# DOC five-axis visualization

UR3e arm geometry and joint descriptions originate from Universal Robots /
`ur_description` 3.5.1, BSD-3-Clause. Original source:
https://github.com/UniversalRobots/Universal_Robots_ROS2_Description
License text: ../../LICENSES/UR-description-BSD-3-Clause.txt.

The first five arm axes and remaining six body meshes are retained; the sixth
UR3e arm joint and wrist3 mesh are removed. Joint names are mapped to joint_1–5.
The lime/black material assignments match the DOC presentation.

Michael Giuseppe Aglieri authored the illustrative laboratory gripper, DOC
integration and mesh export, GPL-3.0-only. The three radial fingers are visual
sliders inspired by ToolBox Robotics EBG-30; they are not manufacturer CAD or its
adaptive mechanism. They do not consume the J6 motor channel.

The model is the visualization already used in the DOC presentation and Webots
laboratory. It is **not the physical EB-15-based DOC CAD**. Uncalibrated UR3e mass
and inertia values have been removed. Nominal home offsets are presentation
alignment only and never command motion. Provenance and mesh hashes are recorded
in provenance.json. Export tool: scripts/import_doc_reference.py.
