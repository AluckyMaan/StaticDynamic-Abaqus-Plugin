# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import math
import os

from abaqus import *
from abaqusConstants import *
from caeModules import *
import regionToolset
import staticDynamicDB


def Main(functionOption='Seismic', Model_name='Model-1',
         soilInstance_name='soil-1', soilPart_name='soil',
         soilSet='Set-soil', depth=0.0, verticalAxis='Y',
         geoType='CSV', stepType='Implicit', stepName='Step-geo',
         wave111='P', theta_a='0,1,0',
         t_time=20.0, d_time=0.01, iterationsNum=20, saveNum=2,
         cpuNum=4, gpuNum=0, initialJobName='',
         NodeSet=True, NodeInfo=False,
         SpringDamping=False, SeismicLoad=False,
         fileName='', autoSubmit=False):
    print('=== Static-Dynamic Analysis v1.0 ===')
    print('Function: %s, Model: %s, Soil: %s' %
          (functionOption, Model_name, soilInstance_name))

    if SpringDamping and not NodeSet:
        print('Error: Spring Damping requires Node Set Establishment.')
        return
    if SeismicLoad and not SpringDamping:
        print('Error: Seismic Load requires Spring Damping.')
        return
    if SeismicLoad and not NodeSet:
        print('Error: Seismic Load requires Node Set Establishment.')
        return

    need_final_analysis = SeismicLoad
    model = get_model(Model_name)
    if model is None:
        return
    instance = get_instance(model, soilInstance_name)
    if instance is None:
        return

    model_dimension = get_model_dimension(model, soilPart_name, instance)
    theta = parse_theta(theta_a)
    mat_props = get_material_properties(model, soilPart_name)
    params = compute_boundary_params(mat_props, depth)
    boundary_faces = get_boundary_node_faces(
        model, instance, soilSet, verticalAxis, model_dimension)
    boundary_nodes = _unique_nodes_from_faces(boundary_faces)

    if NodeSet:
        create_boundary_node_set(model, instance, boundary_nodes, NodeInfo)

    reaction_forces = {}
    if SpringDamping:
        setup_geostatic_equilibrium(model, instance, boundary_nodes, verticalAxis,
                                    stepName, d_time, iterationsNum, saveNum,
                                    model_dimension)
        geo_job_name = run_geostatic_equilibrium_job(
            model, initialJobName, cpuNum, gpuNum)
        reaction_forces = read_boundary_reactions(
            geo_job_name, instance, boundary_nodes, stepName)
        remove_geostatic_temporary_constraints(model)
        apply_viscous_spring_boundary(
            model, instance, boundary_faces, params, verticalAxis,
            model_dimension)
        apply_reaction_balance_loads(
            model, instance, reaction_forces, stepName, model_dimension)

    wave_data = None
    if SeismicLoad and functionOption == 'Seismic':
        wave_data = load_wave_data(geoType, fileName)

    if need_final_analysis:
        setup_steps(model, functionOption, stepName, stepType, t_time, d_time,
                    iterationsNum, saveNum)
    else:
        print('Skipped final analysis step creation.')

    if wave_data and SeismicLoad:
        apply_seismic_load(model, instance, boundary_nodes, wave_data,
                           wave111, theta, verticalAxis)

    if need_final_analysis:
        submit_job(model, initialJobName, cpuNum, gpuNum, autoSubmit)
    else:
        print('Skipped final job creation.')

    print('=== Static-Dynamic Analysis Complete ===')


def get_model(model_name):
    if model_name in mdb.models.keys():
        return mdb.models[model_name]
    print('Error: Model "%s" not found.' % model_name)
    return None


def get_instance(model, instance_name):
    assembly = model.rootAssembly
    if instance_name in assembly.instances.keys():
        return assembly.instances[instance_name]
    print('Error: Instance "%s" not found.' % instance_name)
    return None


def get_model_dimension(model, part_name, instance=None):
    part = model.parts[part_name] if part_name in model.parts.keys() else None
    raw = ''
    if part is not None:
        raw = str(getattr(part, 'space', '') or
                  getattr(part, 'dimensionality', '')).upper()

    if 'TWO_D' in raw or 'AXISYMMETRIC' in raw:
        dimension = '2D'
    elif 'THREE_D' in raw:
        dimension = '3D'
    else:
        dimension = '3D'
        if instance is not None and len(instance.nodes):
            coords = [_node_coords(node) for node in instance.nodes]
            mins = [min([coord[i] for coord in coords]) for i in range(3)]
            maxs = [max([coord[i] for coord in coords]) for i in range(3)]
            spans = [maxs[i] - mins[i] for i in range(3)]
            max_span = max(spans)
            tol = max(1.0e-6, max_span * 1.0e-8)
            if len([span for span in spans if span > tol]) <= 2:
                dimension = '2D'

    print('Model dimension detected: %s' % dimension)
    return dimension


def parse_theta(theta_str):
    try:
        vals = [float(x.strip()) for x in str(theta_str).split(',')]
        if len(vals) != 3:
            raise ValueError
        return vals
    except Exception:
        print('Warning: invalid theta_a, using [0, 1, 0].')
        return [0.0, 1.0, 0.0]


def get_material_properties(model, part_name):
    part = model.parts[part_name] if part_name in model.parts.keys() else None
    if part is None:
        raise ValueError('Part "%s" not found.' % part_name)

    material_name = None
    if part.sectionAssignments:
        section_name = part.sectionAssignments[0].sectionName
        section = model.sections[section_name]
        material_name = getattr(section, 'material', None)
    if not material_name and model.materials:
        material_name = model.materials.keys()[0]
    if not material_name:
        raise ValueError('No material found for part "%s".' % part_name)

    material = model.materials[material_name]
    elastic = material.elastic.table[0]
    density = material.density.table[0][0]
    E = float(elastic[0])
    nu = float(elastic[1])
    rho = float(density)
    G = E / (2.0 * (1.0 + nu))
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    Vp = math.sqrt((lam + 2.0 * G) / rho)
    Vs = math.sqrt(G / rho)

    print('Extracted material properties from: %s' % material_name)
    return {'E': E, 'nu': nu, 'rho': rho, 'G': G, 'lambda': lam,
            'Vp': Vp, 'Vs': Vs}


def compute_boundary_params(mat_props, depth):
    R = float(depth) if float(depth) > 0.0 else 1.0
    params = {
        'K_normal': mat_props['E'] / (2.0 * R),
        'K_shear': mat_props['G'] / (2.0 * R),
        'C_normal': mat_props['rho'] * mat_props['Vp'],
        'C_shear': mat_props['rho'] * mat_props['Vs'],
        'Vp': mat_props['Vp'],
        'Vs': mat_props['Vs'],
    }
    print('Boundary Parameters:')
    print('  K_normal = %.2f, K_shear = %.2f' %
          (params['K_normal'], params['K_shear']))
    print('  C_normal = %.2f, C_shear = %.2f' %
          (params['C_normal'], params['C_shear']))
    print('  Vp = %.2f, Vs = %.2f' % (params['Vp'], params['Vs']))
    return params


def _axis_index(vertical_axis):
    return {'X': 0, 'Y': 1, 'Z': 2}.get(str(vertical_axis).upper(), 1)


def _node_coords(node):
    try:
        coords = tuple(node.coordinates)
    except Exception:
        coords = tuple(node.pointOn[0])
    if len(coords) == 2:
        return (coords[0], coords[1], 0.0)
    if len(coords) < 3:
        return tuple(list(coords) + [0.0] * (3 - len(coords)))
    return coords


def _normal_dof_for_face(face_name, vertical_axis, model_dimension):
    if model_dimension == '2D':
        return 2 if face_name == 'Bottom' else 1
    return _normal_axis_for_face(face_name, vertical_axis) + 1


def _normal_axis_for_face(face_name, vertical_axis):
    face_axis = {
        'Bottom': _axis_index(vertical_axis),
        'XMin': 0,
        'XMax': 0,
        'YMin': 1,
        'YMax': 1,
        'ZMin': 2,
        'ZMax': 2,
    }
    return face_axis.get(face_name, _axis_index(vertical_axis))


def _axis_tributary_widths(values):
    raw_values = sorted([float(v) for v in values])
    if not raw_values:
        return {}
    span = raw_values[-1] - raw_values[0]
    tol = max(1.0e-9, abs(span) * 1.0e-8)

    clusters = []
    for value in raw_values:
        if not clusters or abs(value - clusters[-1][-1]) > tol:
            clusters.append([value])
        else:
            clusters[-1].append(value)

    unique = [sum(cluster) / float(len(cluster)) for cluster in clusters]
    if len(unique) == 1:
        return dict((value, 1.0) for value in raw_values)

    widths = {}
    for i, value in enumerate(unique):
        if i == 0:
            width = 0.5 * (unique[1] - unique[0])
        elif i == len(unique) - 1:
            width = 0.5 * (unique[-1] - unique[-2])
        else:
            width = 0.5 * (unique[i + 1] - unique[i - 1])
        for raw in clusters[i]:
            widths[raw] = abs(width)
    return widths


def _node_boundary_weights(face_nodes, face_name, vertical_axis, model_dimension):
    if not face_nodes:
        return {}

    coords = dict((node.label, _node_coords(node)) for node in face_nodes)
    normal_axis = _normal_axis_for_face(face_name, vertical_axis)
    all_axes = [0, 1, 2]

    if model_dimension == '2D':
        spans = []
        for axis in all_axes:
            values = [coords[node.label][axis] for node in face_nodes]
            spans.append(max(values) - min(values))
        tangent_axes = [
            axis for axis in all_axes
            if axis != normal_axis and spans[axis] > 1.0e-9
        ]
        if not tangent_axes:
            tangent_axes = [max(
                [axis for axis in all_axes if axis != normal_axis],
                key=lambda axis: spans[axis])]
        tangent_axis = tangent_axes[0]
        widths = _axis_tributary_widths(
            [coords[node.label][tangent_axis] for node in face_nodes])
        return dict((node.label, widths[coords[node.label][tangent_axis]])
                    for node in face_nodes)

    spans = []
    for axis in all_axes:
        values = [coords[node.label][axis] for node in face_nodes]
        spans.append(max(values) - min(values))
    tangent_axes = [
        axis for axis in all_axes
        if axis != normal_axis and spans[axis] > 1.0e-9
    ]
    if len(tangent_axes) < 2:
        tangent_axes = sorted(
            [axis for axis in all_axes if axis != normal_axis],
            key=lambda axis: spans[axis],
            reverse=True)[:2]
    widths = {}
    for axis in tangent_axes:
        widths[axis] = _axis_tributary_widths(
            [coords[node.label][axis] for node in face_nodes])

    weights = {}
    for node in face_nodes:
        coord = coords[node.label]
        weight = 1.0
        for axis in tangent_axes:
            weight *= widths[axis][coord[axis]]
        weights[node.label] = weight
    return weights


def _assembly_nodes_from_labels(instance, nodes):
    labels = tuple([node.label for node in nodes])
    return instance.nodes.sequenceFromLabels(labels=labels)


def _node_region(instance, node):
    nodes = instance.nodes.sequenceFromLabels(labels=(node.label,))
    return regionToolset.Region(nodes=nodes)


def _source_nodes_for_boundary(model, instance, soil_set_name):
    assembly = model.rootAssembly
    source_nodes = list(instance.nodes)

    if soil_set_name and soil_set_name in assembly.sets.keys():
        try:
            set_nodes = list(assembly.sets[soil_set_name].nodes)
            if len(set_nodes) >= 0.9 * len(instance.nodes):
                source_nodes = set_nodes
                print('Found full soil set "%s"' % soil_set_name)
            else:
                print('Warning: set "%s" has %d nodes, instance has %d nodes; '
                      'using all instance nodes for artificial boundary detection.' %
                      (soil_set_name, len(set_nodes), len(instance.nodes)))
        except Exception:
            source_nodes = list(instance.nodes)

    if not source_nodes:
        raise ValueError('No soil nodes found.')
    return source_nodes


def get_boundary_node_faces(model, instance, soil_set_name, vertical_axis,
                            model_dimension='3D'):
    source_nodes = _source_nodes_for_boundary(model, instance, soil_set_name)
    vertical_idx = _axis_index(vertical_axis)
    axis_names = ['X', 'Y', 'Z']

    coords = [_node_coords(node) for node in source_nodes]
    mins = [min([coord[i] for coord in coords]) for i in range(3)]
    maxs = [max([coord[i] for coord in coords]) for i in range(3)]
    spans = [maxs[i] - mins[i] for i in range(3)]
    max_span = max(spans)
    tol = max(1.0e-6, max_span * 1.0e-8)
    if model_dimension == '2D' and spans[vertical_idx] <= tol:
        old_axis = axis_names[vertical_idx]
        if spans[1] > tol:
            vertical_idx = 1
        else:
            active = [i for i in (0, 1, 2) if spans[i] > tol]
            if active:
                vertical_idx = active[-1]
        print('Warning: verticalAxis %s has near-zero span in 2D model; using %s.' %
              (old_axis, axis_names[vertical_idx]))

    face_defs = [('Bottom', vertical_idx, mins[vertical_idx])]
    if model_dimension == '2D':
        active_axes = [i for i in (0, 1, 2) if spans[i] > tol]
        if vertical_idx not in active_axes:
            active_axes.append(vertical_idx)
        horizontal = [i for i in active_axes if i != vertical_idx]
        if not horizontal:
            horizontal = sorted(
                [i for i in (0, 1, 2) if i != vertical_idx],
                key=lambda i: spans[i],
                reverse=True)[:1]
        side_idx = horizontal[0]
        face_defs.append((axis_names[side_idx] + 'Min', side_idx, mins[side_idx]))
        face_defs.append((axis_names[side_idx] + 'Max', side_idx, maxs[side_idx]))
    else:
        horizontal = [i for i in (0, 1, 2) if i != vertical_idx]
        for idx in horizontal:
            face_defs.append((axis_names[idx] + 'Min', idx, mins[idx]))
            face_defs.append((axis_names[idx] + 'Max', idx, maxs[idx]))

    faces = {}
    for name, idx, value in face_defs:
        face_nodes = [
            node for node in source_nodes
            if abs(_node_coords(node)[idx] - value) <= tol
        ]
        faces[name] = face_nodes
        print('Boundary face %-6s: %d nodes' % (name, len(face_nodes)))

    boundary_label = '3 artificial boundary edges' if model_dimension == '2D' \
        else '5 artificial boundary faces'
    print('Found %d unique nodes on %s.' %
          (len(_unique_nodes_from_faces(faces)), boundary_label))
    return faces


def _unique_nodes_from_faces(boundary_faces):
    by_label = {}
    for nodes in boundary_faces.values():
        for node in nodes:
            by_label[node.label] = node
    labels = sorted(by_label.keys())
    return [by_label[label] for label in labels]


def get_boundary_nodes(model, instance, soil_set_name, vertical_axis):
    nodes = _unique_nodes_from_faces(
        get_boundary_node_faces(model, instance, soil_set_name, vertical_axis))
    print('Found %d boundary nodes in set "%s"' % (len(nodes), soil_set_name))
    return nodes


def create_boundary_node_set(model, instance, nodes, export_info=False):
    assembly = model.rootAssembly
    assembly_nodes = _assembly_nodes_from_labels(instance, nodes)
    for name in ('ViscousBoundary', 'SD_VisualViscousBoundary'):
        if name in assembly.sets.keys():
            del assembly.sets[name]
    assembly.Set(name='ViscousBoundary', nodes=assembly_nodes)
    print('Created set "ViscousBoundary" with %d nodes.' % len(nodes))

    if export_info:
        path = os.path.join(os.path.dirname(__file__), 'NodeInfo.csv')
        f = open(path, 'wb')
        writer = csv.writer(f)
        writer.writerow(['Label', 'X', 'Y', 'Z'])
        for node in nodes:
            writer.writerow([node.label] + list(node.coordinates))
        f.close()
        print('Node info exported to: %s' % path)


def setup_geostatic_equilibrium(model, instance, nodes, vertical_axis,
                                step_name, d_time, iterations_num, save_num,
                                model_dimension='3D'):
    if step_name not in model.steps.keys():
        model.GeostaticStep(name=step_name, previous='Initial',
                            maxNumInc=int(iterations_num),
                            initialInc=float(d_time), nlgeom=OFF)
        print('Created step: %s (Geostatic)' % step_name)

    _ensure_rf_field_output(model, step_name, save_num)
    assembly = model.rootAssembly
    set_name = 'SD_GeoTempBoundary'
    if set_name in assembly.sets.keys():
        del assembly.sets[set_name]
    assembly.Set(name=set_name, nodes=_assembly_nodes_from_labels(instance, nodes))
    region = assembly.sets[set_name]

    bc_name = 'SD_GeoTempFix'
    if bc_name in model.boundaryConditions.keys():
        del model.boundaryConditions[bc_name]
    if model_dimension == '2D':
        model.DisplacementBC(name=bc_name, createStepName='Initial',
                             region=region, u1=SET, u2=SET, u3=UNSET,
                             ur1=UNSET, ur2=UNSET, ur3=UNSET)
    else:
        model.DisplacementBC(name=bc_name, createStepName='Initial',
                             region=region, u1=SET, u2=SET, u3=SET,
                             ur1=UNSET, ur2=UNSET, ur3=UNSET)
    print('Temporary geostatic boundary fixed %d nodes.' % len(nodes))


def _ensure_rf_field_output(model, step_name, save_num):
    if 'SD_RF_Output' in model.fieldOutputRequests.keys():
        del model.fieldOutputRequests['SD_RF_Output']
    model.FieldOutputRequest(name='SD_RF_Output', createStepName=step_name,
                             variables=('RF', 'U'), frequency=int(save_num))


def run_geostatic_equilibrium_job(model, initial_job_name, cpu_num, gpu_num):
    job_name = (initial_job_name or model.name + '_Job') + '_Geo'
    job = create_analysis_job(model, job_name, cpu_num, gpu_num,
                              'Geostatic equilibrium for boundary reactions',
                              replace=True)
    job.submit(consistencyChecking=OFF)
    print('Geostatic job "%s" submitted.' % job_name)
    job.waitForCompletion()
    print('Geostatic job "%s" finished with status: %s' %
          (job_name, mdb.jobs[job_name].status))
    return job_name


def read_boundary_reactions(job_name, instance, nodes, step_name):
    odb_path = job_name + '.odb'
    if not os.path.isfile(odb_path):
        odb_path = os.path.abspath(odb_path)
    odb = session.openOdb(name=odb_path, readOnly=True)
    reactions = {}
    target_labels = set([node.label for node in nodes])
    try:
        step = odb.steps[step_name]
        frame = step.frames[-1]
        rf = frame.fieldOutputs['RF']
        inst_name = instance.name.upper()
        for value in rf.values:
            if (value.instance.name.upper() == inst_name and
                    value.nodeLabel in target_labels):
                reactions[value.nodeLabel] = tuple(value.data)
    finally:
        odb.close()

    for node in nodes:
        if node.label not in reactions:
            reactions[node.label] = (0.0, 0.0, 0.0)
    print('Read geostatic RF for %d boundary nodes.' % len(reactions))
    return reactions


def remove_geostatic_temporary_constraints(model):
    for name in ('SD_GeoTempFix',):
        if name in model.boundaryConditions.keys():
            del model.boundaryConditions[name]
    print('Temporary geostatic constraints removed.')


def apply_reaction_balance_loads(model, instance, reactions, step_name,
                                 model_dimension='3D'):
    count = 0
    for label, rf in reactions.items():
        node = instance.nodes.sequenceFromLabels(labels=(label,))[0]
        region = _node_region(instance, node)
        name = 'SD_RF_%d' % label
        if name in model.loads.keys():
            del model.loads[name]
        cf1 = -rf[0] if len(rf) > 0 else 0.0
        cf2 = -rf[1] if len(rf) > 1 else 0.0
        cf3 = -rf[2] if model_dimension != '2D' and len(rf) > 2 else 0.0
        model.ConcentratedForce(name=name, createStepName=step_name,
                                region=region, cf1=cf1, cf2=cf2,
                                cf3=cf3, distributionType=UNIFORM,
                                field='', localCsys=None)
        count += 1
    print('Applied equivalent geostatic RF nodal loads: %d' % count)


def apply_viscous_spring_boundary(model, instance, nodes, params, vertical_axis,
                                  model_dimension='3D'):
    assembly = model.rootAssembly
    ef = assembly.engineeringFeatures

    if isinstance(nodes, dict):
        boundary_faces = nodes
        all_nodes = _unique_nodes_from_faces(boundary_faces)
    else:
        boundary_faces = {'Bottom': list(nodes)}
        all_nodes = list(nodes)

    set_name = 'SD_VisualViscousBoundary'
    if set_name in assembly.sets.keys():
        del assembly.sets[set_name]
    assembly.Set(name=set_name, nodes=_assembly_nodes_from_labels(instance, all_nodes))

    for old_name in list(ef.springDashpots.keys()):
        if old_name.startswith('SD_VisualVS_'):
            del ef.springDashpots[old_name]
    for old_set in list(assembly.sets.keys()):
        if old_set.startswith('SD_VS_Face_') or old_set.startswith('SD_VS_Group_'):
            del assembly.sets[old_set]

    active_faces = 0
    created_groups = 0
    for face_name in sorted(boundary_faces.keys()):
        face_nodes = boundary_faces[face_name]
        if not face_nodes:
            continue
        normal_dof = _normal_dof_for_face(
            face_name, vertical_axis, model_dimension)
        active_dofs = (1, 2) if model_dimension == '2D' else (1, 2, 3)
        if normal_dof not in active_dofs:
            print('  Warning: skipped %s; normal DOF %d is outside %s model DOFs.' %
                  (face_name, normal_dof, model_dimension))
            continue
        active_faces += 1
        shear_dofs = [d for d in active_dofs if d != normal_dof]
        specs = [('Normal', normal_dof, params['K_normal'], params['C_normal'])]
        if model_dimension == '2D':
            specs.append(('Shear', shear_dofs[0], params['K_shear'], params['C_shear']))
        else:
            specs.append(('Shear1', shear_dofs[0], params['K_shear'], params['C_shear']))
            specs.append(('Shear2', shear_dofs[1], params['K_shear'], params['C_shear']))

        face_set = 'SD_VS_Face_%s' % face_name
        assembly.Set(name=face_set,
                     nodes=_assembly_nodes_from_labels(instance, face_nodes))
        weights = _node_boundary_weights(
            face_nodes, face_name, vertical_axis, model_dimension)
        if weights:
            values = weights.values()
            print('  %s influence %s: min=%.6g max=%.6g total=%.6g' %
                  (face_name,
                   'length' if model_dimension == '2D' else 'area',
                   min(values), max(values), sum(values)))

        for comp_name, dof, base_stiffness, base_dashpot in specs:
            grouped = {}
            for node in face_nodes:
                influence = weights.get(node.label, 1.0)
                stiffness = influence * base_stiffness
                dashpot = influence * base_dashpot
                key = ('%.12g' % stiffness, '%.12g' % dashpot)
                grouped.setdefault(key, []).append(node)

            for index, key in enumerate(sorted(grouped.keys()), 1):
                group_nodes = grouped[key]
                stiffness = float(key[0])
                dashpot = float(key[1])
                group_set = 'SD_VS_Group_%s_%s_%03d' % (
                    face_name, comp_name, index)
                assembly.Set(
                    name=group_set,
                    nodes=_assembly_nodes_from_labels(instance, group_nodes))
                region = assembly.sets[group_set]
                feature_name = 'SD_VisualVS_%s_%s_%03d' % (
                    face_name, comp_name, index)
                ef.SpringDashpotToGround(
                    name=feature_name,
                    region=region,
                    orientation=None,
                    dof=dof,
                    springBehavior=ON,
                    springStiffness=stiffness,
                    dashpotBehavior=ON,
                    dashpotCoefficient=dashpot)
                created_groups += 1
                print('Created visual SpringDashpotToGround: %s DOF=%d nodes=%d A*K=%.6g A*C=%.6g' %
                      (feature_name, dof, len(group_nodes), stiffness, dashpot))

    boundary_kind = 'edges' if model_dimension == '2D' else 'faces'
    print('Visual viscous-spring boundary applied to %d unique nodes on %d %s (%d weighted groups).' %
          (len(all_nodes), active_faces, boundary_kind, created_groups))


def load_wave_data(geo_type, file_path=''):
    search_files = []
    if file_path:
        if os.path.isfile(file_path):
            search_files.append(file_path)
        else:
            print('Warning: wave file not found: %s' % file_path)

    if not search_files:
        search_dir = os.path.dirname(__file__) or '.'
        for filename in os.listdir(search_dir):
            lower = filename.lower()
            if lower.endswith('.csv') or lower.endswith('.xlsx') or lower.endswith('.xls'):
                if 'vel' in lower or 'dis' in lower or 'acc' in lower:
                    search_files.append(os.path.join(search_dir, filename))

    result = {}
    for path in search_files:
        lower = os.path.basename(path).lower()
        try:
            data = staticDynamicDB.read_wave_data(path, geo_type)
        except Exception as e:
            print('Warning: Failed to read wave file "%s": %s' % (path, e))
            continue
        if not data:
            continue
        if 'acc' in lower:
            result['acceleration'] = data
            kind = 'acceleration'
        elif 'vel' in lower:
            result['velocity'] = data
            kind = 'velocity'
        elif 'dis' in lower:
            result['displacement'] = data
            kind = 'displacement'
        else:
            result['velocity'] = data
            kind = 'velocity'
        print('Loaded %s data: %s (%d points)' % (kind, path, len(data)))

    if result.get('acceleration'):
        return result['acceleration']
    if result.get('velocity'):
        return result['velocity']
    if result.get('displacement'):
        return result['displacement']
    print('Warning: no valid wave data found; seismic load skipped.')
    return None


def setup_steps(model, function_option, step_name, step_type,
                t_time, d_time, iterations_num, save_num):
    previous = step_name if step_name in model.steps.keys() else 'Initial'
    analysis_step = 'Step-dynamic' if function_option == 'Seismic' else 'Step-static'
    if analysis_step in model.steps.keys():
        return
    if function_option == 'Seismic' and step_type == 'Implicit':
        model.ImplicitDynamicsStep(name=analysis_step, previous=previous,
                                   timePeriod=float(t_time),
                                   maxNumInc=int(iterations_num),
                                   initialInc=float(d_time))
    elif function_option == 'Seismic' and step_type == 'Explicit':
        model.ExplicitDynamicsStep(name=analysis_step, previous=previous,
                                   timePeriod=float(t_time))
    else:
        model.StaticStep(name=analysis_step, previous=previous,
                         timePeriod=float(t_time),
                         maxNumInc=int(iterations_num),
                         initialInc=float(d_time))
    set_field_outputs(model, save_num)
    print('Created step: %s' % analysis_step)


def set_field_outputs(model, save_num):
    for request in model.fieldOutputRequests.values():
        request.setValues(frequency=int(save_num))


def apply_seismic_load(model, instance, nodes, wave_data, wave_type, theta, vertical_axis):
    step_name = 'Step-dynamic'
    if step_name not in model.steps.keys():
        print('Warning: dynamic step not found; seismic load skipped.')
        return
    amp_name = 'SD_Wave_Amplitude'
    if amp_name in model.amplitudes.keys():
        del model.amplitudes[amp_name]
    model.TabularAmplitude(name=amp_name, timeSpan=STEP, smooth=SOLVER_DEFAULT,
                           data=tuple(wave_data))
    print('Created seismic amplitude "%s" with %d points.' %
          (amp_name, len(wave_data)))


def create_analysis_job(model, job_name, cpu_num, gpu_num, description, replace=False):
    if not job_name:
        job_name = model.name + '_Job'
    if job_name in mdb.jobs.keys():
        if replace:
            del mdb.jobs[job_name]
        else:
            return mdb.jobs[job_name]

    return mdb.Job(name=job_name, model=model.name, description=description,
                   type=ANALYSIS, atTime=None, waitMinutes=0, waitHours=0,
                   queue=None, memory=90, memoryUnits=PERCENTAGE,
                   getMemoryFromAnalysis=True, explicitPrecision=SINGLE,
                   nodalOutputPrecision=SINGLE, echoPrint=OFF,
                   modelPrint=OFF, contactPrint=OFF, historyPrint=OFF,
                   userSubroutine='', scratch='', resultsFormat=ODB,
                   parallelizationMethodExplicit=DOMAIN,
                   numDomains=int(cpu_num), activateLoadBalancing=False,
                   multiprocessingMode=DEFAULT, numCpus=int(cpu_num),
                   numGPUs=int(gpu_num))


def submit_job(model, job_name, cpu_num, gpu_num, auto_submit=False):
    job = create_analysis_job(
        model, job_name or model.name + '_StaticDynamic',
        cpu_num, gpu_num,
        'Static-Dynamic Analysis with Viscous-Spring Boundary',
        replace=True)
    print('Job "%s" created with %d CPUs, %d GPUs.' %
          (job.name, int(cpu_num), int(gpu_num)))
    if auto_submit:
        job.submit(consistencyChecking=OFF)
        print('Job "%s" submitted.' % job.name)
        job.waitForCompletion()
        print('Job "%s" finished with status: %s' %
              (job.name, mdb.jobs[job.name].status))
