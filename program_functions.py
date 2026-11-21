# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Function signatures, isolated call frames and diagnostics. No execution or I/O."""
from collections import namedtuple
from program_lang import check_name, parse

MAX_FUNCTIONS = 32
MAX_PARAMETERS = 8
MAX_CALL_DEPTH = 8
CallFrame = namedtuple('CallFrame', 'pc variables loops repeats function definition call result')

def validate_block(block):
    kind = block['kind']
    if kind in ('function', 'call'):
        check_name(block.get('function'), 'Nome funzione')
    if kind == 'function':
        params = block.get('parameters', [])
        if not isinstance(params, list) or len(params) > MAX_PARAMETERS:
            raise ValueError('Una funzione ammette al massimo 8 parametri.')
        for name in params: check_name(name, 'Nome parametro')
        if len(set(params)) != len(params): raise ValueError('Parametri della funzione duplicati.')
        block['parameters'] = params[:]
    elif kind == 'call':
        args = block.get('arguments', {})
        if not isinstance(args, dict) or len(args) > MAX_PARAMETERS:
            raise ValueError('Argomenti della chiamata non validi.')
        normalized = {}
        for name, value in args.items():
            check_name(name, 'Nome argomento')
            if type(value) not in (str, int, float, bool): raise ValueError('Un argomento deve essere un’espressione numerica.')
            text = str(value).strip(); parse(text); normalized[name] = text
        block['arguments'] = normalized
        if block.get('result'): check_name(block['result'], 'Variabile risultato')
        else: block.pop('result', None)
    elif kind == 'return':
        value = block.get('value', '')
        if type(value) not in (str, int, float, bool): raise ValueError('Risultato della funzione non valido.')
        block['value'] = str(value).strip()
        if block['value']: parse(block['value'])


def definitions(blocks, match):
    result = {}
    for index, block in enumerate(blocks):
        if block['kind'] != 'function': continue
        name = block['function']
        if name in result: raise ValueError('Funzione duplicata: '+name)
        result[name] = dict(index=index, end=match[index]['end'], block=block)
        if len(result) > MAX_FUNCTIONS: raise ValueError('Massimo 32 funzioni nel progetto.')
    return result


def enter(state, block, index, library, known, sensors):
    name = block['function']; definition = library.get(name)
    if not definition or not definition['block']['enabled']:
        raise ValueError('Funzione assente o disabilitata: '+name)
    if any(frame.function == name for frame in state.calls): raise ValueError('Ricorsione non ammessa: '+name)
    if len(state.calls) >= MAX_CALL_DEPTH: raise ValueError('Chiamate annidate oltre 8 livelli.')
    params = definition['block']['parameters']; args = block['arguments']
    if set(params) != set(args):
        missing = sorted(set(params)-set(args)); extra = sorted(set(args)-set(params))
        raise ValueError('Argomenti di %s non corrispondenti; mancanti: %s; inattesi: %s.' % (name, ', '.join(missing) or '—', ', '.join(extra) or '—'))
    if set(params) & set(sensors): raise ValueError('Un parametro coincide con un sensore: '+', '.join(sorted(set(params) & set(sensors))))
    if block.get('result') in sensors: raise ValueError('La variabile risultato coincide con un sensore: '+block['result'])
    # Evaluate ALL arguments in the caller before creating the isolated local scope.
    values = {param: known(args[param], state.variables) for param in params}
    frame = CallFrame(index+1, tuple(sorted(state.variables.items())), state.loops, state.repeats, name,
                      definition['index'], index, block.get('result', ''))
    state.calls += (frame,); state.variables = values; state.loops = (); state.repeats = (); state.pc = definition['index']+1


def leave(state, value=None):
    if not state.calls: raise ValueError('Restituisci è ammesso soltanto dentro una funzione.')
    frame = state.calls[-1]
    if frame.result and value is None: raise ValueError('La funzione %s non restituisce un valore per %s.' % (frame.function, frame.result))
    state.calls = state.calls[:-1]; state.pc = frame.pc; state.variables = dict(frame.variables)
    state.loops = frame.loops; state.repeats = frame.repeats
    if frame.result: state.variables[frame.result] = value


def trace(calls):
    return [dict(function=f.function, definition=f.definition, call_index=f.call,
                 iteration=repr((f.loops, f.repeats))) for f in calls]


def location(path):
    return ' / '.join('Richiamo %d → %s' % (f['call_index']+1, f['function']) for f in path)
