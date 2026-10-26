# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Local URDF arm description, forward kinematics and position-only preview IK.
No serial, subprocess, network, xacro execution or motion authority.
"""
import copy, hashlib, json, math, re, shutil, uuid
from pathlib import Path
import xml.etree.ElementTree as ET


def number(value, low=-1e8, high=1e8):
    if isinstance(value, bool): raise ValueError('Numero non valido.')
    value=float(value)
    if not math.isfinite(value) or not low <= value <= high: raise ValueError('Numero fuori intervallo.')
    return value


def vector(text, default, size=3):
    values=list(default) if text is None else [number(v) for v in text.split()]
    if len(values)!=size: raise ValueError('Vettore URDF non valido.')
    return values


def identity(): return [[float(i==j) for j in range(4)] for i in range(4)]
def multiply(a,b): return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
def origin(xyz=(0,0,0),rpy=(0,0,0)):
    r,p,y=rpy; cr,sr,cp,sp,cy,sy=math.cos(r),math.sin(r),math.cos(p),math.sin(p),math.cos(y),math.sin(y)
    return [[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr,xyz[0]],
            [sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr,xyz[1]],[-sp,cp*sr,cp*cr,xyz[2]],[0,0,0,1]]
def rotation(axis,angle):
    x,y,z=axis; c,s=math.cos(angle),math.sin(angle); t=1-c
    return [[t*x*x+c,t*x*y-s*z,t*x*z+s*y,0],[t*x*y+s*z,t*y*y+c,t*y*z-s*x,0],[t*x*z-s*y,t*y*z+s*x,t*z*z+c,0],[0,0,0,1]]
def element_origin(element):
    e=element.find('origin')
    return dict(xyz=vector(e.get('xyz') if e is not None else None,[0,0,0]),rpy=vector(e.get('rpy') if e is not None else None,[0,0,0]))
def xml_root(raw):
    if len(raw)>5_000_000: raise ValueError('URDF oltre 5 MB.')
    if re.search(br'<!\s*(DOCTYPE|ENTITY)',raw,re.I): raise ValueError('DTD ed entità esterne non sono consentite.')
    try: root=ET.fromstring(raw)
    except ET.ParseError as error: raise ValueError('XML URDF non valido: '+str(error)) from error
    if root.tag!='robot' or any('xacro' in str(e.tag) for e in root.iter()): raise ValueError('Importa un URDF già espanso, non un file Xacro.')
    return root


def resolve_mesh(filename, base):
    if not filename or '\x00' in filename: return None
    base=Path(base).resolve()
    if filename.startswith('package://'):
        parts=Path(filename[10:]).parts
        if len(parts)<2 or '..' in parts: return None
        package,*relative=parts
        candidates=[]
        for directory in [base,*list(base.parents)[:3]]:
            if directory.name==package:candidates.append(directory.joinpath(*relative))
            candidates.append(directory/package/Path(*relative))
            candidates.append(directory/'share'/package/Path(*relative))
    elif filename.startswith('file://'): candidates=[Path(filename[7:])]
    elif '://' in filename: return None
    else:candidates=[base/filename]
    # Only the selected package and its immediate project roots may supply assets.
    allowed=base.parent.resolve()
    for p in candidates:
        try:
            p=p.resolve()
            if not p.is_relative_to(allowed) or not p.is_file() or p.stat().st_size>30_000_000:continue
            if p.suffix.lower() not in ('.stl','.obj','.dae'):continue
            return p
        except OSError:pass
    return None


def parse_urdf(raw, base=None, asset_folder=None):
    root=xml_root(raw); links={}; joints=[]; warnings=[]; materials={}
    for material in root.findall('material'):
        color=material.find('color')
        if color is not None:materials[material.get('name','')]=vector(color.get('rgba'),[.66,1,.16,1],4)
    for element in root.findall('link'):
        name=element.get('name','')
        if not name or len(name)>128 or name in links:raise ValueError('Nome link mancante o duplicato.')
        visuals=[]
        for visual in element.findall('visual')[:20]:
            geometry=visual.find('geometry')
            if geometry is None or len(geometry)!=1:continue
            g=geometry[0]; item=dict(kind=g.tag,**element_origin(visual),color=[.66,1,.16,1],size=[.04,.04,.04],mesh='')
            m=visual.find('material')
            if m is not None:
                c=m.find('color');item['color']=vector(c.get('rgba'),item['color'],4) if c is not None else materials.get(m.get('name',''),item['color'])
            item['color']=[number(v,0,1) for v in item['color']]
            if g.tag=='box':item['size']=[number(v,.000001,20) for v in vector(g.get('size'),[.04]*3)]
            elif g.tag=='cylinder':item['size']=[number(g.get('radius'),.000001,10),number(g.get('length'),.000001,20),0]
            elif g.tag=='sphere':item['size']=[number(g.get('radius'),.000001,10),0,0]
            elif g.tag=='mesh':
                item['size']=vector(g.get('scale'),[1,1,1]);filename=g.get('filename','');item['source_mesh']=filename
                mesh=resolve_mesh(filename,base) if base else None
                if mesh and asset_folder:
                    destination=Path(asset_folder)/('asset-'+hashlib.sha256(mesh.read_bytes()).hexdigest()[:20]+mesh.suffix.lower())
                    if not destination.exists():
                        if mesh.suffix.lower()=='.obj':
                            cleaned='\n'.join(line for line in mesh.read_text(errors='replace').splitlines() if not line.lstrip().startswith(('mtllib ','usemtl ')))
                            destination.write_text(cleaned)
                        elif mesh.suffix.lower()=='.dae':
                            content=mesh.read_bytes()
                            if re.search(br'<!\s*(DOCTYPE|ENTITY)',content,re.I):raise ValueError('DTD non consentita nella mesh DAE.')
                            tree=ET.fromstring(content)
                            for parent in tree.iter():
                                for child in list(parent):
                                    if child.tag.split('}')[-1] in ('library_images','extra'):parent.remove(child)
                                for key,value in parent.attrib.items():
                                    if key in ('url','source') and ('://' in value or (value and not value.startswith('#'))):raise ValueError('Riferimento esterno non consentito nella mesh DAE.')
                            destination.write_bytes(ET.tostring(tree))
                        else:shutil.copyfile(mesh,destination)
                    item['mesh']=str(destination)
                else:warnings.append('Mesh non disponibile: '+filename+'; visualizzazione con segnaposto.')
            else:warnings.append('Geometria ignorata: '+g.tag);continue
            visuals.append(item)
        links[name]=dict(name=name,visuals=visuals)
    if not links or len(links)>256:raise ValueError('Servono da 1 a 256 link.')
    seen=set(); children=set(); names=set()
    for element in root.findall('joint'):
        name=element.get('name','');kind=element.get('type','')
        parent=element.find('parent');child=element.find('child')
        p=parent.get('link') if parent is not None else None;c=child.get('link') if child is not None else None
        if not name or name in names or p not in links or c not in links or c in children or p==c:raise ValueError('Albero dei giunti non valido.')
        if kind not in ('fixed','revolute','continuous','prismatic'):raise ValueError('Questa versione supporta bracci con giunti fixed/revolute/continuous/prismatic.')
        names.add(name);children.add(c)
        axis=element.find('axis');v=vector(axis.get('xyz') if axis is not None else None,[1,0,0]);norm=math.sqrt(sum(x*x for x in v))
        if norm<1e-9:raise ValueError('Asse del giunto nullo.')
        limit=element.find('limit');lo,hi=(-math.pi,math.pi) if kind!='prismatic' else (0,.1)
        if kind=='continuous':lo,hi=-2*math.pi,2*math.pi
        elif kind!='fixed':
            if limit is not None:lo,hi=number(limit.get('lower',lo)),number(limit.get('upper',hi))
            else:warnings.append('Limiti assenti per '+name+': intervallo di anteprima provvisorio.')
        if lo>hi:raise ValueError('Limiti invertiti: '+name)
        mimic=element.find('mimic')
        joint=dict(name=name,kind=kind,parent=p,child=c,axis=[x/norm for x in v],lower=lo,upper=hi,**element_origin(element),mimic='',multiplier=1.,mimic_offset=0.)
        if mimic is not None:joint.update(mimic=mimic.get('joint',''),multiplier=number(mimic.get('multiplier',1)),mimic_offset=number(mimic.get('offset',0)))
        joints.append(joint)
    roots=set(links)-children
    if len(roots)!=1:raise ValueError('L’URDF deve avere una sola base e un albero connesso.')
    base_link=next(iter(roots));ordered=[];pending=joints[:];reached={base_link};depths={base_link:0}
    while pending:
        ready=[j for j in pending if j['parent'] in reached]
        if not ready:raise ValueError('Ciclo o link scollegati nell’URDF.')
        for j in ready:
            ordered.append(j);pending.remove(j);reached.add(j['child']);depths[j['child']]=depths[j['parent']]+(j['kind']!='fixed' and not j['mimic'])
    if reached!=set(links):raise ValueError('Link scollegati nell’URDF.')
    by_name={j['name']:j for j in ordered}
    for joint in ordered:
        visited={joint['name']};m=joint['mimic']
        while m:
            if m not in by_name or m in visited:raise ValueError('Catena mimic non valida.')
            visited.add(m);m=by_name[m]['mimic']
    actuated=[j for j in ordered if j['kind']!='fixed' and not j['mimic']]
    if not 1<=len(actuated)<=16:raise ValueError('Importa un braccio con 1–16 giunti indipendenti.')
    # Reject multiple articulated arms/legs; short terminal gripper branches are allowed.
    for link in links:
        branches=[j for j in ordered if j['parent']==link]
        long_branches=0
        for branch in branches:
            descendants={branch['child']}
            for j in ordered:
                if j['parent'] in descendants:descendants.add(j['child'])
            if sum(j['kind']!='fixed' and not j['mimic'] for j in ordered if j['child'] in descendants)>1:long_branches+=1
        if long_branches>1:raise ValueError('Rilevate più catene articolate: gli umanoidi e i robot multi-braccio saranno supportati in futuro.')
    leaves=set(links)-{j['parent'] for j in ordered};tip=max(leaves,key=lambda link:(depths[link],link))
    extension=root.find('robot_console');extra={}
    if extension is not None:
        fingers=extension.get('gripper_joints','').split()
        if any(name not in by_name for name in fingers):raise ValueError('Giunti pinza non validi.')
        extra=dict(reference=extension.get('reference','')[:80],gripper=dict(joints=fingers,travel=number(extension.get('gripper_travel',0),0,.1)),nominal_home=[number(v,-7,7) for v in extension.get('nominal_home','').split()])
        if extension.get('tip') in links:tip=extension.get('tip')
    return dict(**extra,schema=1,name=root.get('name','Braccio importato')[:100],root=base_link,tip=tip,links=list(links.values()),joints=ordered,warnings=warnings,source_hash=hashlib.sha256(raw).hexdigest(),approximate=False)


def default_urdf(axes=5):
    root=ET.Element('robot',name='Braccio · modello schematico '+str(axes)+' DOF')
    def link(name,length,width,color):
        element=ET.SubElement(root,'link',name=name);visual=ET.SubElement(element,'visual')
        ET.SubElement(visual,'origin',xyz=f'0 0 {length/2}')
        geometry=ET.SubElement(visual,'geometry');ET.SubElement(geometry,'box',size=f'{width} {width} {length}')
        material=ET.SubElement(visual,'material',name='doc');ET.SubElement(material,'color',rgba=color)
    link('base',.10,.14,'0.08 0.10 0.07 1')
    lengths=[.10,.22,.20,.08,.10]+([.06] if axes==6 else [])
    for i,length in enumerate(lengths):
        link('link_'+str(i+1),length,.065 if i<3 else .045,'0.66 1 0.16 1' if i%2==0 else '0.08 0.10 0.07 1')
        j=ET.SubElement(root,'joint',name='joint_'+str(i+1),type='revolute')
        ET.SubElement(j,'parent',link='base' if i==0 else 'link_'+str(i));ET.SubElement(j,'child',link='link_'+str(i+1))
        ET.SubElement(j,'origin',xyz=f'0 0 {0.10 if i==0 else lengths[i-1]}',rpy='0 0.55 0' if i==1 else ('0 -1.10 0' if i==2 else '0 0 0'))
        ET.SubElement(j,'axis',xyz='0 0 1' if i in (0,3) else '0 1 0');ET.SubElement(j,'limit',lower=str(-math.pi),upper=str(math.pi),effort='1',velocity='0.35')
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def frames(model, positions, calibration=None):
    calibration=calibration or {};result={model['root']:identity()};by_name={j['name']:j for j in model['joints']}
    values={}
    def value(name):
        if name in values:return values[name]
        j=by_name[name]
        gripper=model.get('gripper',{})
        if name in gripper.get('joints',[]):v=float(positions.get('__gripper',0))*gripper['travel']
        elif j['mimic']:v=value(j['mimic'])*j['multiplier']+j['mimic_offset']
        else:
            c=calibration.get(name,{})
            v=float(positions.get(name,0))*c.get('sign',1)+c.get('offset',0)
        values[name]=v;return v
    for j in model['joints']:
        t=origin(j['xyz'],j['rpy']);v=value(j['name']) if j['kind']!='fixed' else 0
        if j['kind']=='prismatic':t=multiply(t,origin([x*v for x in j['axis']]))
        elif j['kind']!='fixed':t=multiply(t,rotation(j['axis'],v))
        result[j['child']]=multiply(result[j['parent']],t)
    return result


def tcp(model, positions, calibration=None, tip=None, tool=(0,0,0)):
    f=frames(model,positions,calibration)[tip or model['tip']]
    return [sum(f[i][k]*tool[k] for k in range(3))+f[i][3] for i in range(3)]


def position_ik(model, positions, target, enabled, calibration=None, tip=None, tool=(0,0,0)):
    target=[number(v,-10,10) for v in target];q=dict(positions)
    if len(target)!=3:raise ValueError('Il target cartesiano richiede X, Y e Z.')
    joints=[j for j in model['joints'] if j['kind']!='fixed' and not j['mimic'] and enabled.get(j['name'],True)]
    def solve3(a,b):
        a=[row[:]+[v] for row,v in zip(a,b)]
        for i in range(3):
            pivot=max(range(i,3),key=lambda k:abs(a[k][i]));a[i],a[pivot]=a[pivot],a[i]
            if abs(a[i][i])<1e-14:return [0,0,0]
            n=a[i][i];a[i]=[v/n for v in a[i]]
            for k in range(3):
                if k!=i:
                    n=a[k][i];a[k]=[v-n*w for v,w in zip(a[k],a[i])]
        return [a[i][3] for i in range(3)]
    for iteration in range(180):
        current=tcp(model,q,calibration,tip,tool);error=[a-b for a,b in zip(target,current)]
        distance=math.sqrt(sum(e*e for e in error))
        if distance<.001:return dict(positions=q,error_m=distance,converged=True,iterations=iteration)
        jac=[]
        for j in joints:
            trial=q.copy();trial[j['name']]=trial.get(j['name'],0)+1e-5
            point=tcp(model,trial,calibration,tip,tool);jac.append([(a-b)/1e-5 for a,b in zip(point,current)])
        a=[[sum(column[i]*column[k] for column in jac)+(.002 if i==k else 0) for k in range(3)] for i in range(3)]
        delta=solve3(a,error)
        for j,column in zip(joints,jac):
            step=max(-.15,min(.15,sum(x*y for x,y in zip(column,delta))))
            # Limits belong to the URDF coordinate, after calibration.
            c=(calibration or {}).get(j['name'],{});sign=c.get('sign',1);offset=c.get('offset',0)
            lo,hi=sorted(((j['lower']-offset)/sign,(j['upper']-offset)/sign))
            q[j['name']]=max(lo,min(hi,q.get(j['name'],0)+step))
    return dict(positions=q,error_m=distance,converged=False,iterations=180)
