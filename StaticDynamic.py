# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import datetime
import math
import os

from abaqus import *
from abaqusConstants import *
from caeModules import *
import regionToolset
import staticDynamicDB

try:
    import __builtin__ as _builtins
except ImportError:
    import builtins as _builtins

# Abaqus also exports a name called sum; the plugin needs Python's numeric sum.
sum = _builtins.sum

__version__ = '0.4.0-dev'
MAX_TRAVELING_DELAY_BINS = 200


class StaticDynamicRunReport(object):
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or os.path.dirname(__file__) or '.'
        self.started_at = datetime.datetime.now()
        self.rows = []
        self.status = 'STARTED'

    def add(self, section, name, value='', note=''):
        self.rows.append((
            _report_value(section),
            _report_value(name),
            _report_value(value),
            _report_value(note),
        ))

    def add_message(self, level, message):
        self.add('Message', level, message)

    def set_status(self, status):
        self.status = str(status)

    def write(self):
        finished_at = datetime.datetime.now()
        csv_path = os.path.join(self.output_dir, 'StaticDynamic_run_report.csv')
        txt_path = os.path.join(self.output_dir, 'StaticDynamic_run_report.txt')

        rows = [
            ('Run', 'version', __version__, ''),
            ('Run', 'started_at', self.started_at.strftime('%Y-%m-%d %H:%M:%S'), ''),
            ('Run', 'finished_at', finished_at.strftime('%Y-%m-%d %H:%M:%S'), ''),
            ('Run', 'status', self.status, ''),
        ] + self.rows

        f = open(csv_path, 'wb')
        try:
            writer = csv.writer(f)
            writer.writerow(['section', 'name', 'value', 'note'])
            for row in rows:
                writer.writerow(list(row))
        finally:
            f.close()

        f = open(txt_path, 'w')
        try:
            f.write('StaticDynamic Run Report\n')
            f.write('Version: %s\n' % __version__)
            f.write('Status: %s\n' % self.status)
            f.write('Started: %s\n' %
                    self.started_at.strftime('%Y-%m-%d %H:%M:%S'))
            f.write('Finished: %s\n\n' %
                    finished_at.strftime('%Y-%m-%d %H:%M:%S'))
            current_section = None
            for section, name, value, note in self.rows:
                if section != current_section:
                    current_section = section
                    f.write('[%s]\n' % section)
                line = '  %s: %s' % (name, value)
                if note:
                    line += ' (%s)' % note
                f.write(line + '\n')
        finally:
            f.close()

        print('Run report exported to: %s' % txt_path)
        return csv_path, txt_path


def _report_value(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return '%.12g' % value
    try:
        return str(value)
    except Exception:
        return repr(value)


def _safe_log_text(value):
    if value is None:
        return ''
    try:
        return str(value)
    except UnicodeEncodeError:
        try:
            escaped = value.encode('unicode_escape')
            try:
                return escaped.decode('ascii')
            except Exception:
                return escaped
        except Exception:
            return repr(value)
    except Exception:
        return repr(value)


def _report_inputs(report, kwargs):
    for name in sorted(kwargs.keys()):
        report.add('Input', name, kwargs[name])


def _vector_magnitude(vector):
    try:
        vals = [float(item) for item in vector]
    except Exception:
        return 0.0
    return math.sqrt(sum([item * item for item in vals]))


def _validate_main_inputs(model, instance, part_name, soil_set_name, depth,
                          NodeSet, NodeInfo, SpringDamping, SeismicLoad,
                          function_option,
                          geostatic_file_type, geostatic_file, step_name,
                          balance_tolerance, geo_type, wave_file,
                          model_length_unit, incident_vector,
                          wave_input_mode, propagation_vector,
                          apparent_wave_velocity, delay_bin_size, report):
    errors = []
    warnings = []

    if not (NodeSet or NodeInfo or SpringDamping or SeismicLoad):
        errors.append('Select at least one function option.')
    if NodeInfo and not NodeSet:
        errors.append('Node Information requires Node Set Establishment.')
    if SpringDamping and not NodeSet:
        errors.append('Spring Damping requires Node Set Establishment.')
    if SeismicLoad and not SpringDamping:
        errors.append('Seismic Load requires Spring Damping.')
    if SeismicLoad and function_option != 'Seismic':
        errors.append('Seismic Load requires Function Option = Seismic.')

    if part_name not in model.parts.keys():
        errors.append('Part "%s" not found in model "%s".' %
                      (part_name, model.name))
    if len(instance.nodes) == 0:
        errors.append('Instance "%s" has no mesh nodes.' % instance.name)

    try:
        depth_value = float(depth)
    except Exception:
        depth_value = 0.0
    if SpringDamping and depth_value <= 0.0:
        errors.append('Structure Depth must be greater than 0 when Spring Damping is enabled.')

    try:
        tol_value = float(balance_tolerance)
    except Exception:
        tol_value = 0.0
    if SpringDamping and tol_value <= 0.0:
        errors.append('Balance Tol must be greater than 0 when Spring Damping is enabled.')

    if soil_set_name and soil_set_name not in model.rootAssembly.sets.keys():
        warnings.append('Soil set "%s" not found; boundary detection will use all instance nodes.' %
                        soil_set_name)

    source = normalize_geostatic_file_type(geostatic_file_type)
    if SpringDamping:
        if not step_name:
            errors.append('Geostatic Step Name is required for Spring Damping.')
        if not geostatic_file:
            errors.append('A geostatic ODB or CSV file is required for Spring Damping.')
        elif not os.path.isfile(geostatic_file):
            errors.append('Geostatic file not found: %s' % geostatic_file)
        else:
            lower = geostatic_file.lower()
            if source == 'ODB' and not lower.endswith('.odb'):
                errors.append('Geostatic Source is ODB, but the selected file is not an .odb file.')
            if source == 'CSV' and not lower.endswith('.csv'):
                errors.append('Geostatic Source is CSV, but the selected file is not a .csv file.')

    if SeismicLoad and wave_file and not os.path.isfile(wave_file):
        if not os.path.isdir(wave_file):
            warnings.append('Wave file not found; plugin will search DIS/VEL/ACC files in the plugin folder.')

    if SeismicLoad:
        try:
            staticDynamicDB._model_length_unit_scale(model_length_unit)
        except Exception:
            errors.append('Unsupported Model Length Unit "%s"; use m, cm, or mm.' %
                          model_length_unit)
        incident = _parse_vector_components(incident_vector)
        if incident is None or _vector_magnitude(incident) <= 1.0e-20:
            errors.append('Incident Vector must be a non-zero x,y,z vector.')
        mode = normalize_wave_input_mode(wave_input_mode)
        if mode == 'Traveling':
            try:
                if float(apparent_wave_velocity) <= 0.0:
                    errors.append('Traveling wave input requires Apparent Velocity greater than 0.')
            except Exception:
                errors.append('Traveling wave input requires a numeric Apparent Velocity.')
            if str(propagation_vector or '').strip():
                propagation = _parse_vector_components(propagation_vector)
                if propagation is None or _vector_magnitude(propagation) <= 1.0e-20:
                    errors.append('Propagation Vector must be a non-zero x,y,z vector.')
        elif mode == 'LayeredSite':
            warnings.append('LayeredSite input uses model material Vs along the vertical axis; Apparent Velocity is ignored.')
        try:
            if float(delay_bin_size) < 0.0:
                errors.append('Delay Bin Size cannot be negative.')
        except Exception:
            errors.append('Delay Bin Size must be numeric.')

    for message in warnings:
        print('Warning: ' + message)
        if report is not None:
            report.add_message('WARNING', message)
    for message in errors:
        print('Error: ' + message)
        if report is not None:
            report.add_message('ERROR', message)
    if report is not None:
        report.add('Preflight', 'errors', len(errors))
        report.add('Preflight', 'warnings', len(warnings))
    return errors, warnings

def Main(functionOption='Seismic', Model_name='Model-1',
         soilInstance_name='soil-1', soilPart_name='soil',
         soilSet='Set-soil', depth=0.0, verticalAxis='Y',
         geoType='PEER', stepType='Implicit', stepName='Step-geo',
         wave111='P', theta_a='0,1,0',
         modelLengthUnit='m',
         waveInputMode='Uniform', propagationVector='',
         apparentWaveVelocity=0.0, delayBinSize=0.0,
         t_time=20.0, d_time=0.01, iterationsNum=20, saveNum=2,
         cpuNum=4, gpuNum=0, initialJobName='',
         NodeSet=True, NodeInfo=False,
         SpringDamping=False, SeismicLoad=False,
         fileName='', autoSubmit=False,
         geostaticFileType='ODB', geostaticFile='',
         balanceTolerance=1.0e-4):
    report = StaticDynamicRunReport()
    input_kwargs = {
        'functionOption': functionOption,
        'Model_name': Model_name,
        'soilInstance_name': soilInstance_name,
        'soilPart_name': soilPart_name,
        'soilSet': soilSet,
        'depth': depth,
        'verticalAxis': verticalAxis,
        'geoType': geoType,
        'stepType': stepType,
        'stepName': stepName,
        'wave111': wave111,
        'theta_a': theta_a,
        'modelLengthUnit': modelLengthUnit,
        'waveInputMode': waveInputMode,
        'propagationVector': propagationVector,
        'apparentWaveVelocity': apparentWaveVelocity,
        'delayBinSize': delayBinSize,
        't_time': t_time,
        'd_time': d_time,
        'iterationsNum': iterationsNum,
        'saveNum': saveNum,
        'cpuNum': cpuNum,
        'gpuNum': gpuNum,
        'initialJobName': initialJobName,
        'NodeSet': NodeSet,
        'NodeInfo': NodeInfo,
        'SpringDamping': SpringDamping,
        'SeismicLoad': SeismicLoad,
        'fileName': fileName,
        'autoSubmit': autoSubmit,
        'geostaticFileType': geostaticFileType,
        'geostaticFile': geostaticFile,
        'balanceTolerance': balanceTolerance,
    }
    _report_inputs(report, input_kwargs)

    print('=== Static-Dynamic Analysis v%s ===' % __version__)
    print('Function: %s, Model: %s, Soil: %s' %
          (functionOption, Model_name, soilInstance_name))

    report_written = False
    try:
        need_final_analysis = SeismicLoad
        model = get_model(Model_name)
        if model is None:
            report.add_message('ERROR', 'Model "%s" not found.' % Model_name)
            report.set_status('FAILED')
            report.write()
            report_written = True
            return
        instance = get_instance(model, soilInstance_name)
        if instance is None:
            report.add_message('ERROR', 'Instance "%s" not found.' %
                               soilInstance_name)
            report.set_status('FAILED')
            report.write()
            report_written = True
            return

        errors, warnings = _validate_main_inputs(
            model, instance, soilPart_name, soilSet, depth,
            NodeSet, NodeInfo, SpringDamping, SeismicLoad,
            functionOption, geostaticFileType, geostaticFile, stepName,
            balanceTolerance, geoType, fileName, modelLengthUnit,
            theta_a, waveInputMode, propagationVector,
            apparentWaveVelocity, delayBinSize, report)
        if errors:
            report.set_status('FAILED')
            report.write()
            report_written = True
            return

        model_dimension = get_model_dimension(model, soilPart_name, instance)
        report.add('Model', 'dimension', model_dimension)
        theta = parse_theta(theta_a)
        report.add('Model', 'incident_vector', theta)
        propagation = parse_vector(
            propagationVector, _vertical_axis_vector(verticalAxis))
        report.add('Model', 'propagation_vector', propagation)

        boundary_faces = get_boundary_node_faces(
            model, instance, soilSet, verticalAxis, model_dimension)
        boundary_nodes = _unique_nodes_from_faces(boundary_faces)
        report.add('Boundary', 'unique_nodes', len(boundary_nodes))
        for face_name in sorted(boundary_faces.keys()):
            face_nodes = boundary_faces[face_name]
            weights = _node_boundary_weights(
                face_nodes, face_name, verticalAxis, model_dimension)
            total_weight = sum(weights.values()) if weights else 0.0
            report.add('BoundaryFace', face_name + '.nodes', len(face_nodes))
            report.add('BoundaryFace', face_name + '.total_weight',
                       total_weight,
                       'length' if model_dimension == '2D' else 'area')
        if not boundary_nodes:
            report.add_message('ERROR', 'No artificial boundary nodes found.')
            report.set_status('FAILED')
            report.write()
            report_written = True
            return

        params = None
        node_params = {}
        if SpringDamping or NodeInfo:
            try:
                mat_props = get_material_properties(model, soilPart_name)
                params = compute_boundary_params(mat_props, depth)
                node_params = build_boundary_node_params(
                    model, soilPart_name, boundary_nodes, depth, params,
                    verticalAxis)
                report.add('Material', 'fallback', params.get('material', ''))
                report.add('Material', 'Vp', params.get('Vp', ''))
                report.add('Material', 'Vs', params.get('Vs', ''))
                report.add('Material', 'node_param_entries', len(node_params))
            except Exception as e:
                message = 'Material and boundary parameter setup failed: %s' % e
                if SpringDamping:
                    print('Error: ' + message)
                    report.add_message('ERROR', message)
                    report.set_status('FAILED')
                    report.write()
                    report_written = True
                    return
                print('Warning: ' + message)
                report.add_message('WARNING', message)

        if NodeSet:
            create_boundary_node_set(model, instance, boundary_nodes, False,
                                     report=report)
        if NodeInfo:
            export_boundary_info_csv(
                model, instance, boundary_faces, node_params,
                verticalAxis, model_dimension, report=report)

        reaction_forces = {}
        if SpringDamping:
            geostatic_file = geostaticFile
            geostatic_source = normalize_geostatic_file_type(geostaticFileType)
            report.add('Geostatic', 'source', geostatic_source)
            if geostatic_source == 'ODB':
                if not check_geostatic_balance_from_odb(
                        geostatic_file, instance, stepName, balanceTolerance,
                        report=report):
                    message = 'Geostatic balance check failed; boundary conversion stopped.'
                    print('Error: ' + message)
                    report.add_message('ERROR', message)
                    report.set_status('FAILED')
                    report.write()
                    report_written = True
                    return
                reaction_forces = read_boundary_reactions_from_odb(
                    geostatic_file, instance, boundary_nodes, stepName,
                    report=report)
            else:
                message = ('CSV reaction input cannot verify displacement balance; '
                           'ensure the source model satisfies the geostatic tolerance.')
                print('Warning: ' + message)
                report.add_message('WARNING', message)
                reaction_forces = read_boundary_reactions_from_csv(
                    geostatic_file, boundary_nodes, report=report)
            apply_viscous_spring_boundary(
                model, instance, boundary_faces, params, verticalAxis,
                model_dimension, node_params, report=report)
            if reaction_forces:
                ensure_reaction_balance_step(model, stepName, report=report)
                apply_reaction_balance_loads(
                    model, instance, reaction_forces, stepName,
                    model_dimension, report=report)
            else:
                print('Skipped reaction-balance loads.')
                report.add('ReactionBalance', 'loads_applied', 0,
                           'no reaction forces were read')

        wave_data = None
        if SeismicLoad and functionOption == 'Seismic':
            wave_data = load_wave_data(
                geoType, fileName, modelLengthUnit, report=report)
            if wave_data is None:
                message = 'Seismic Load is enabled, but no valid wave data was found.'
                print('Error: ' + message)
                report.add_message('ERROR', message)
                report.set_status('FAILED')
                report.write()
                report_written = True
                return

        if need_final_analysis:
            setup_steps(model, functionOption, stepName, stepType, t_time,
                        d_time, iterationsNum, saveNum, report=report)
        else:
            print('Skipped final analysis step creation.')
            report.add('Analysis', 'final_step', 'skipped')

        if wave_data and SeismicLoad:
            apply_seismic_load(
                model, instance, boundary_faces, params, wave_data, wave111,
                theta, verticalAxis, model_dimension, node_params,
                waveInputMode, propagation, apparentWaveVelocity,
                delayBinSize, report=report)

        if need_final_analysis:
            submit_job(model, initialJobName, cpuNum, gpuNum, autoSubmit,
                       report=report)
        else:
            print('Skipped final job creation.')
            report.add('Job', 'final_job', 'skipped')

        orient_view_to_vertical_axis(model, instance, verticalAxis)
        report.set_status('SUCCESS')
        report.write()
        report_written = True
        print('=== Static-Dynamic Analysis Complete ===')
    except Exception as e:
        report.add_message('ERROR', 'Unhandled exception: %s' % e)
        report.set_status('FAILED')
        if not report_written:
            report.write()
            report_written = True
        raise


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


def _parse_vector_components(vector_str):
    text = str(vector_str or '').strip()
    if not text:
        return None
    try:
        vals = [float(x.strip()) for x in text.split(',')]
        if len(vals) != 3:
            return None
        return vals
    except Exception:
        return None


def parse_vector(vector_str, fallback):
    text = str(vector_str or '').strip()
    if not text:
        return list(fallback)
    try:
        vals = [float(x.strip()) for x in text.split(',')]
        if len(vals) != 3:
            raise ValueError
        return vals
    except Exception:
        print('Warning: invalid vector "%s", using fallback %s.' %
              (_safe_log_text(vector_str), fallback))
        return list(fallback)


def _vertical_axis_vector(vertical_axis):
    axis = str(vertical_axis or 'Y').upper()
    if axis == 'X':
        return [1.0, 0.0, 0.0]
    if axis == 'Z':
        return [0.0, 0.0, 1.0]
    return [0.0, 1.0, 0.0]


def normalize_wave_input_mode(mode):
    text = str(mode or 'Uniform').strip().lower()
    compact = text.replace('-', '').replace('_', '').replace(' ', '')
    if compact in ('layeredsite', 'site', 'sitecolumn', 'freefield'):
        return 'LayeredSite'
    if text in ('traveling', 'travelling', 'incident', 'oblique'):
        return 'Traveling'
    return 'Uniform'


def normalize_geostatic_file_type(file_type):
    text = str(file_type or '').strip().upper()
    if text == 'CSV':
        return 'CSV'
    return 'ODB'


def get_material_properties(model, part_name):
    part = model.parts[part_name] if part_name in model.parts.keys() else None
    if part is None:
        raise ValueError('Part "%s" not found.' % part_name)

    material_name = None
    if part.sectionAssignments:
        section_name = part.sectionAssignments[0].sectionName
        material_name = _section_material_name(model, section_name)
    if not material_name and model.materials:
        material_name = model.materials.keys()[0]
    if not material_name:
        raise ValueError('No material found for part "%s".' % part_name)

    return get_material_properties_by_name(model, material_name)


def get_material_properties_by_name(model, material_name, verbose=True):
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

    if verbose:
        print('Extracted material properties from: %s' % material_name)
    return {'E': E, 'nu': nu, 'rho': rho, 'G': G, 'lambda': lam,
            'Vp': Vp, 'Vs': Vs, 'material': material_name}


def compute_boundary_params(mat_props, depth, verbose=True):
    R = float(depth) if float(depth) > 0.0 else 1.0
    params = {
        'K_normal': mat_props['E'] / (2.0 * R),
        'K_shear': mat_props['G'] / (2.0 * R),
        'C_normal': mat_props['rho'] * mat_props['Vp'],
        'C_shear': mat_props['rho'] * mat_props['Vs'],
        'Vp': mat_props['Vp'],
        'Vs': mat_props['Vs'],
        'material': mat_props.get('material', 'Material'),
    }
    if verbose:
        print('Boundary Parameters:')
        print('  Material = %s' % params['material'])
        print('  K_normal = %.2f, K_shear = %.2f' %
              (params['K_normal'], params['K_shear']))
        print('  C_normal = %.2f, C_shear = %.2f' %
              (params['C_normal'], params['C_shear']))
        print('  Vp = %.2f, Vs = %.2f' % (params['Vp'], params['Vs']))
    return params


def _section_material_name(model, section_name):
    if section_name not in model.sections.keys():
        return None
    section = model.sections[section_name]
    return getattr(section, 'material', None)


def _resolve_region(region, part=None):
    if isinstance(region, tuple) and region and isinstance(region[0], str):
        region_name = region[0]
        for container_name in ('sets', 'allInternalSets'):
            try:
                container = getattr(part, container_name)
                if region_name in container.keys():
                    return container[region_name]
            except Exception:
                pass
    return region


def _region_elements(region, part=None):
    region = _resolve_region(region, part)
    try:
        return list(region.elements)
    except Exception:
        return []


def _region_cells(region, part=None):
    region = _resolve_region(region, part)
    try:
        return list(region.cells)
    except Exception:
        return []


def _element_node_labels(elem):
    try:
        return [node.label for node in elem.getNodes()]
    except Exception:
        try:
            return list(elem.connectivity)
        except Exception:
            return []


def _element_centroid(elem, node_coords_by_label):
    labels = _element_node_labels(elem)
    coords = [node_coords_by_label[label]
              for label in labels if label in node_coords_by_label]
    if not coords:
        return None
    return tuple(sum(coord[i] for coord in coords) / float(len(coords))
                 for i in range(3))


def _cell_point(cell):
    try:
        point = cell.pointOn[0]
    except Exception:
        return None
    if len(point) == 2:
        return (point[0], point[1], 0.0)
    if len(point) < 3:
        return tuple(list(point) + [0.0] * (3 - len(point)))
    return point


def _cluster_layer_points(layer_points):
    if not layer_points:
        return []
    ordered = sorted(layer_points, key=lambda item: item[0])
    span = ordered[-1][0] - ordered[0][0]
    tol = max(1.0e-9, abs(span) * 1.0e-8)
    clusters = []
    for value, material_name in ordered:
        if not clusters or abs(value - clusters[-1][-1][0]) > tol:
            clusters.append([(value, material_name)])
        else:
            clusters[-1].append((value, material_name))

    result = []
    for cluster in clusters:
        center = sum(item[0] for item in cluster) / float(len(cluster))
        counts = {}
        for _, material_name in cluster:
            counts[material_name] = counts.get(material_name, 0) + 1
        result.append((center, _dominant_material(counts)))
    return result


def _material_from_layer_centers(value, layer_centers):
    if not layer_centers:
        return None
    if len(layer_centers) == 1:
        return layer_centers[0][1]
    for i in range(len(layer_centers) - 1):
        boundary = 0.5 * (layer_centers[i][0] + layer_centers[i + 1][0])
        if value <= boundary:
            return layer_centers[i][1]
    return layer_centers[-1][1]


def _cell_layer_element_materials(model, part, assignments, vertical_axis):
    vertical_idx = _axis_index(vertical_axis)
    layer_points = []
    for assignment in assignments:
        material_name = _section_material_name(model, assignment.sectionName)
        if not material_name:
            continue
        for cell in _region_cells(assignment.region, part):
            point = _cell_point(cell)
            if point is not None:
                layer_points.append((float(point[vertical_idx]), material_name))

    layer_centers = _cluster_layer_points(layer_points)
    if not layer_centers:
        return {}

    node_coords_by_label = dict((node.label, _node_coords(node))
                                for node in part.nodes)
    elem_material = {}
    for elem in part.elements:
        centroid = _element_centroid(elem, node_coords_by_label)
        if centroid is None:
            continue
        material_name = _material_from_layer_centers(
            centroid[vertical_idx], layer_centers)
        if material_name:
            elem_material[elem.label] = material_name

    if elem_material:
        print('Layered boundary grouping uses section cell positions along %s.' %
              str(vertical_axis).upper())
        for center, material_name in layer_centers:
            print('  Layer center %.6g -> %s' % (center, material_name))
    return elem_material


def _part_element_materials(model, part, vertical_axis):
    elem_material = {}
    assignments = list(part.sectionAssignments)
    if not assignments:
        return elem_material

    for assignment in assignments:
        material_name = _section_material_name(model, assignment.sectionName)
        if not material_name:
            continue
        elements = _region_elements(assignment.region, part)
        for elem in elements:
            elem_material[elem.label] = material_name

    if not elem_material:
        elem_material = _cell_layer_element_materials(
            model, part, assignments, vertical_axis)

    if not elem_material and len(assignments) == 1:
        material_name = _section_material_name(model, assignments[0].sectionName)
        if material_name:
            for elem in part.elements:
                elem_material[elem.label] = material_name

    if not elem_material and assignments:
        material_name = _section_material_name(model, assignments[0].sectionName)
        if material_name:
            print('Warning: could not map section regions to mesh elements; '
                  'using first section material "%s" for boundary nodes.' %
                  material_name)
            for elem in part.elements:
                elem_material[elem.label] = material_name

    return elem_material


def _node_material_counts(part, elem_material):
    counts_by_node = {}
    for elem in part.elements:
        material_name = elem_material.get(elem.label)
        if not material_name:
            continue
        for node_label in _element_node_labels(elem):
            counts = counts_by_node.setdefault(node_label, {})
            counts[material_name] = counts.get(material_name, 0) + 1
    return counts_by_node


def _dominant_material(material_counts):
    if not material_counts:
        return None
    items = sorted(material_counts.items(), key=lambda item: (-item[1], item[0]))
    return items[0][0]


def build_boundary_node_params(model, part_name, boundary_nodes, depth,
                               fallback_params, vertical_axis='Y'):
    part = model.parts[part_name] if part_name in model.parts.keys() else None
    if part is None:
        return {}

    elem_material = _part_element_materials(model, part, vertical_axis)
    if not elem_material:
        print('Layered boundary grouping skipped: no element-material map found.')
        return {}

    counts_by_node = _node_material_counts(part, elem_material)
    params_by_material = {}
    node_params = {}
    material_weight_summary = {}
    split_nodes = 0
    fallback_material = fallback_params.get('material', 'Material')

    for node in boundary_nodes:
        material_counts = counts_by_node.get(node.label, {})
        if not material_counts:
            material_counts = {fallback_material: 1}
        total = float(sum(material_counts.values()))
        entries = []
        if len(material_counts) > 1:
            split_nodes += 1
        for material_name in sorted(material_counts.keys()):
            if material_name not in params_by_material:
                if material_name in model.materials.keys():
                    props = get_material_properties_by_name(
                        model, material_name, verbose=False)
                    params_by_material[material_name] = compute_boundary_params(
                        props, depth, verbose=False)
                else:
                    params_by_material[material_name] = fallback_params
            fraction = material_counts[material_name] / total
            entries.append((params_by_material[material_name], fraction))
            material_weight_summary[material_name] = \
                material_weight_summary.get(material_name, 0.0) + fraction
        node_params[node.label] = entries

    print('Layered boundary material groups:')
    for material_name in sorted(material_weight_summary.keys()):
        params = params_by_material[material_name]
        print('  %s: equivalent_nodes=%.2f, Vp=%.2f, Vs=%.2f' %
              (material_name, material_weight_summary[material_name],
               params['Vp'], params['Vs']))
    if split_nodes:
        print('  Interface boundary nodes split by adjacent material counts: %d' %
              split_nodes)
    return node_params


def _axis_index(vertical_axis):
    return {'X': 0, 'Y': 1, 'Z': 2}.get(str(vertical_axis).upper(), 1)


def orient_view_to_vertical_axis(model, instance=None, vertical_axis='Y'):
    try:
        viewport_name = session.currentViewportName
        viewport = session.viewports[viewport_name]
    except Exception:
        return

    try:
        viewport.setValues(displayedObject=model.rootAssembly)
    except Exception:
        pass

    try:
        axis = str(vertical_axis).upper()
        up_vectors = {
            'X': (1.0, 0.0, 0.0),
            'Y': (0.0, 1.0, 0.0),
            'Z': (0.0, 0.0, 1.0),
        }
        view_vectors = {
            'X': (-0.6, 1.0, -1.0),
            'Y': (-1.0, 0.6, -1.0),
            'Z': (-1.0, 1.0, 0.6),
        }
        up = up_vectors.get(axis, up_vectors['Y'])
        view_vector = view_vectors.get(axis, view_vectors['Y'])
        viewport.view.setViewpoint(
            viewVector=view_vector,
            cameraUpVector=up)
        viewport.view.fitView()
        print('Viewport oriented with %s as vertical axis.' % axis)
    except Exception as e:
        print('Warning: failed to orient viewport: %s' % e)
        try:
            viewport.view.fitView()
        except Exception:
            pass


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


def create_boundary_node_set(model, instance, nodes, export_info=False,
                             report=None):
    assembly = model.rootAssembly
    assembly_nodes = _assembly_nodes_from_labels(instance, nodes)
    for name in ('ViscousBoundary', 'SD_VisualViscousBoundary'):
        if name in assembly.sets.keys():
            del assembly.sets[name]
    assembly.Set(name='ViscousBoundary', nodes=assembly_nodes)
    print('Created set "ViscousBoundary" with %d nodes.' % len(nodes))
    if report is not None:
        report.add('NodeSet', 'ViscousBoundary.nodes', len(nodes))

    if export_info:
        path = os.path.join(os.path.dirname(__file__), 'NodeInfo.csv')
        f = open(path, 'wb')
        writer = csv.writer(f)
        writer.writerow(['Label', 'X', 'Y', 'Z'])
        for node in nodes:
            writer.writerow([node.label] + list(node.coordinates))
        f.close()
        print('Node info exported to: %s' % path)
        if report is not None:
            report.add('Output', 'NodeInfo.csv', path)


def export_boundary_info_csv(model, instance, boundary_faces, node_params,
                             vertical_axis, model_dimension='3D',
                             report=None):
    path = os.path.join(os.path.dirname(__file__), 'BoundaryInfo.csv')
    material_by_node = {}
    weight_by_face = {}
    for face_name, face_nodes in boundary_faces.items():
        weights = _node_boundary_weights(
            face_nodes, face_name, vertical_axis, model_dimension)
        weight_by_face[face_name] = weights
        for node in face_nodes:
            entries = node_params.get(node.label, [])
            materials = []
            for params, fraction in entries:
                materials.append('%s:%.6g' %
                                 (params.get('material', 'Material'), fraction))
            material_by_node[(face_name, node.label)] = '|'.join(materials)

    f = open(path, 'wb')
    try:
        writer = csv.writer(f)
        writer.writerow([
            'nodeLabel', 'x', 'y', 'z', 'faceName',
            'materialFractions', 'areaOrLength'
        ])
        for face_name in sorted(boundary_faces.keys()):
            weights = weight_by_face.get(face_name, {})
            for node in sorted(boundary_faces[face_name],
                               key=lambda item: item.label):
                coords = _node_coords(node)
                writer.writerow([
                    node.label, coords[0], coords[1], coords[2], face_name,
                    material_by_node.get((face_name, node.label), ''),
                    weights.get(node.label, 1.0)
                ])
    finally:
        f.close()
    print('Boundary info exported to: %s' % path)
    if report is not None:
        report.add('Output', 'BoundaryInfo.csv', path)
        report.add('Output', 'BoundaryInfo.rows',
                   sum([len(nodes) for nodes in boundary_faces.values()]))
    return path


def export_seismic_arrival_info_csv(instance, boundary_faces, arrival_delays,
                                    report=None):
    path = os.path.join(os.path.dirname(__file__),
                        'SeismicArrivalInfo.csv')
    rows = 0
    f = open(path, 'wb')
    try:
        writer = csv.writer(f)
        writer.writerow([
            'nodeLabel', 'x', 'y', 'z', 'faceName', 'arrivalDelay'
        ])
        for face_name in sorted(boundary_faces.keys()):
            for node in sorted(boundary_faces[face_name],
                               key=lambda item: item.label):
                coords = _node_coords(node)
                writer.writerow([
                    node.label, coords[0], coords[1], coords[2], face_name,
                    arrival_delays.get(node.label, 0.0)
                ])
                rows += 1
    finally:
        f.close()
    print('Seismic arrival info exported to: %s' % path)
    if report is not None:
        report.add('Output', 'SeismicArrivalInfo.csv', path)
        report.add('Output', 'SeismicArrivalInfo.rows', rows)
    return path


def export_seismic_site_profile_csv(profile, report=None):
    path = os.path.join(os.path.dirname(__file__),
                        'SeismicSiteProfile.csv')
    rows = 0
    f = open(path, 'wb')
    try:
        writer = csv.writer(f)
        writer.writerow([
            'verticalCoordinate', 'equivalentVs',
            'cumulativeTravelTime', 'sampleCount'
        ])
        for row in profile:
            writer.writerow([
                row.get('coord', 0.0),
                row.get('Vs', 0.0),
                row.get('travelTime', 0.0),
                row.get('samples', 0)
            ])
            rows += 1
    finally:
        f.close()
    print('Seismic site profile exported to: %s' % path)
    if report is not None:
        report.add('Output', 'SeismicSiteProfile.csv', path)
        report.add('Output', 'SeismicSiteProfile.rows', rows)
    return path


def check_geostatic_balance_from_odb(odb_path, instance, step_name,
                                     tolerance=1.0e-4, report=None):
    if not odb_path:
        raise ValueError('Geostatic ODB file is required.')
    if not os.path.isfile(odb_path):
        raise ValueError('Geostatic ODB file not found: %s' % odb_path)

    odb = session.openOdb(name=odb_path, readOnly=True)
    try:
        if step_name not in odb.steps.keys():
            raise ValueError('Step "%s" not found in ODB "%s".' %
                             (step_name, odb_path))
        frame = odb.steps[step_name].frames[-1]
        if 'U' not in frame.fieldOutputs.keys():
            raise ValueError('U field output not found in ODB "%s", step "%s".' %
                             (odb_path, step_name))
        if 'RF' not in frame.fieldOutputs.keys():
            raise ValueError('RF field output not found in ODB "%s", step "%s".' %
                             (odb_path, step_name))

        inst_name = instance.name.upper()
        max_u = 0.0
        max_label = None
        count = 0
        for value in frame.fieldOutputs['U'].values:
            if value.instance.name.upper() != inst_name:
                continue
            count += 1
            squared = 0.0
            for item in value.data:
                squared += float(item) * float(item)
            magnitude = math.sqrt(squared)
            if magnitude > max_u:
                max_u = magnitude
                max_label = value.nodeLabel

        if count == 0:
            raise ValueError('No U values found for instance "%s" in ODB "%s".' %
                             (instance.name, odb_path))
        print('Geostatic balance check: Umax=%.6g at node %s, tolerance=%.6g' %
              (max_u, str(max_label), float(tolerance)))
        if report is not None:
            report.add('Geostatic', 'Umax', max_u)
            report.add('Geostatic', 'Umax_node', max_label)
            report.add('Geostatic', 'balance_tolerance', float(tolerance))
            report.add('Geostatic', 'balance_passed',
                       max_u <= float(tolerance))
        return max_u <= float(tolerance)
    finally:
        odb.close()


def read_boundary_reactions_from_odb(odb_path, instance, nodes, step_name,
                                     report=None):
    if not odb_path:
        raise ValueError('Geostatic ODB file is required.')
    if not os.path.isfile(odb_path):
        raise ValueError('Geostatic ODB file not found: %s' % odb_path)
    odb = session.openOdb(name=odb_path, readOnly=True)
    reactions = {}
    target_labels = set([node.label for node in nodes])
    try:
        if step_name not in odb.steps.keys():
            raise ValueError('Step "%s" not found in ODB "%s".' %
                             (step_name, odb_path))
        step = odb.steps[step_name]
        frame = step.frames[-1]
        if 'RF' not in frame.fieldOutputs.keys():
            raise ValueError('RF field output not found in ODB "%s", step "%s".' %
                             (odb_path, step_name))
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
    print('Read geostatic RF for %d boundary nodes from: %s' %
          (len(reactions), odb_path))
    if report is not None:
        report.add('Geostatic', 'reaction_nodes', len(reactions))
        report.add('Geostatic', 'reaction_file', odb_path)
    return reactions


def read_boundary_reactions_from_csv(csv_path, nodes, report=None):
    if not csv_path:
        raise ValueError('Geostatic CSV file is required.')
    if not os.path.isfile(csv_path):
        raise ValueError('Geostatic CSV file not found: %s' % csv_path)

    target_labels = set([node.label for node in nodes])
    reactions = {}
    header_map = None
    f = open(csv_path, 'rb')
    try:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            cells = [str(item).strip() for item in row]
            if not cells or not cells[0] or cells[0].startswith('#'):
                continue
            if header_map is None:
                lower = [item.lower() for item in cells]
                if ('nodelabel' in lower or 'node_label' in lower or
                        'label' in lower or 'node' in lower):
                    header_map = _reaction_csv_header_map(lower)
                    continue
                header_map = {'label': 0, 'rf1': 1, 'rf2': 2, 'rf3': 3}
            try:
                label = int(float(cells[header_map['label']]))
                if label not in target_labels:
                    continue
                rf1 = _csv_float(cells, header_map.get('rf1'))
                rf2 = _csv_float(cells, header_map.get('rf2'))
                rf3 = _csv_float(cells, header_map.get('rf3'))
                reactions[label] = (rf1, rf2, rf3)
            except Exception:
                continue
    finally:
        f.close()

    missing = 0
    for node in nodes:
        if node.label not in reactions:
            reactions[node.label] = (0.0, 0.0, 0.0)
            missing += 1
    print('Read geostatic RF for %d boundary nodes from CSV: %s (missing filled as zero: %d)' %
          (len(reactions), csv_path, missing))
    if report is not None:
        report.add('Geostatic', 'reaction_nodes', len(reactions))
        report.add('Geostatic', 'reaction_file', csv_path)
        report.add('Geostatic', 'missing_reaction_nodes', missing)
    return reactions


def _reaction_csv_header_map(lower_header):
    candidates = {
        'label': ('nodelabel', 'node_label', 'label', 'node'),
        'rf1': ('rf1', 'rfx', 'cf1', 'fx'),
        'rf2': ('rf2', 'rfy', 'cf2', 'fy'),
        'rf3': ('rf3', 'rfz', 'cf3', 'fz'),
    }
    result = {}
    for key, names in candidates.items():
        for name in names:
            if name in lower_header:
                result[key] = lower_header.index(name)
                break
    if 'label' not in result:
        result['label'] = 0
    if 'rf1' not in result:
        result['rf1'] = 1
    if 'rf2' not in result:
        result['rf2'] = 2
    if 'rf3' not in result:
        result['rf3'] = 3
    return result


def _csv_float(cells, index):
    if index is None or index >= len(cells):
        return 0.0
    try:
        return float(cells[index])
    except Exception:
        return 0.0


def ensure_reaction_balance_step(model, step_name, report=None):
    if step_name in model.steps.keys():
        if report is not None:
            report.add('ReactionBalance', 'target_step', step_name,
                       'existing')
        return
    model.StaticStep(name=step_name, previous='Initial', nlgeom=OFF)
    print('Created reaction-balance target step: %s' % step_name)
    if report is not None:
        report.add('ReactionBalance', 'target_step', step_name, 'created')


def apply_reaction_balance_loads(model, instance, reactions, step_name,
                                 model_dimension='3D', report=None):
    count = 0
    skipped = 0
    for label, rf in reactions.items():
        name = 'SD_RF_%d' % label
        if name in model.loads.keys():
            del model.loads[name]
        cf1 = -rf[0] if len(rf) > 0 else 0.0
        cf2 = -rf[1] if len(rf) > 1 else 0.0
        cf3 = -rf[2] if model_dimension != '2D' and len(rf) > 2 else 0.0
        if max(abs(cf1), abs(cf2), abs(cf3)) <= 1.0e-12:
            skipped += 1
            continue
        node = instance.nodes.sequenceFromLabels(labels=(label,))[0]
        region = _node_region(instance, node)
        model.ConcentratedForce(name=name, createStepName=step_name,
                                region=region, cf1=cf1, cf2=cf2,
                                cf3=cf3, distributionType=UNIFORM,
                                field='', localCsys=None)
        count += 1
    print('Applied equivalent geostatic RF nodal loads: %d (skipped zero RF: %d)' %
          (count, skipped))
    if report is not None:
        report.add('ReactionBalance', 'loads_applied', count)
        report.add('ReactionBalance', 'zero_rf_skipped', skipped)
    return {'loads_applied': count, 'zero_rf_skipped': skipped}


def apply_viscous_spring_boundary(model, instance, nodes, params, vertical_axis,
                                  model_dimension='3D', node_params=None,
                                  report=None):
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
        specs = [('Normal', normal_dof, 'K_normal', 'C_normal')]
        if model_dimension == '2D':
            specs.append(('Shear', shear_dofs[0], 'K_shear', 'C_shear'))
        else:
            specs.append(('Shear1', shear_dofs[0], 'K_shear', 'C_shear'))
            specs.append(('Shear2', shear_dofs[1], 'K_shear', 'C_shear'))

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
            if report is not None:
                report.add('SpringDashpot', face_name + '.weight_min',
                           min(values))
                report.add('SpringDashpot', face_name + '.weight_max',
                           max(values))
                report.add('SpringDashpot', face_name + '.weight_total',
                           sum(values))

        for comp_name, dof, stiffness_key, dashpot_key in specs:
            grouped = {}
            for node in face_nodes:
                local_entries = [(params, 1.0)]
                if node_params and node.label in node_params:
                    local_entries = node_params[node.label]
                    if isinstance(local_entries, dict):
                        local_entries = [(local_entries, 1.0)]
                for local_params, material_fraction in local_entries:
                    influence = weights.get(node.label, 1.0) * material_fraction
                    stiffness = influence * local_params[stiffness_key]
                    dashpot = influence * local_params[dashpot_key]
                    material_name = local_params.get('material', 'Material')
                    key = ('%.12g' % stiffness, '%.12g' % dashpot, material_name)
                    grouped.setdefault(key, []).append(node)

            for index, key in enumerate(sorted(grouped.keys()), 1):
                group_nodes = grouped[key]
                stiffness = float(key[0])
                dashpot = float(key[1])
                material_name = key[2]
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
                print('Created visual SpringDashpotToGround: %s material=%s DOF=%d nodes=%d A*K=%.6g A*C=%.6g' %
                      (feature_name, material_name, dof, len(group_nodes), stiffness, dashpot))

    boundary_kind = 'edges' if model_dimension == '2D' else 'faces'
    print('Visual viscous-spring boundary applied to %d unique nodes on %d %s (%d weighted groups).' %
          (len(all_nodes), active_faces, boundary_kind, created_groups))
    if report is not None:
        report.add('SpringDashpot', 'unique_nodes', len(all_nodes))
        report.add('SpringDashpot', 'active_faces', active_faces)
        report.add('SpringDashpot', 'weighted_groups', created_groups)
    return {'unique_nodes': len(all_nodes), 'active_faces': active_faces,
            'weighted_groups': created_groups}


def _wave_kind_from_filename(path):
    lower = os.path.basename(path).lower()
    ext = os.path.splitext(lower)[1]
    if ext == '.at2' or 'acc' in lower:
        return 'acceleration'
    if ext == '.vt2' or 'vel' in lower:
        return 'velocity'
    if ext == '.dt2' or 'dis' in lower or 'disp' in lower:
        return 'displacement'
    return 'velocity'


def _series_meta(data, path, kind, source_unit='model units', scale=1.0):
    dt = 0.0
    if len(data) >= 2:
        dt = float(data[1][0]) - float(data[0][0])
    return {
        'kind': kind,
        'sourcePath': path,
        'sourceUnit': source_unit,
        'scale': scale,
        'npts': len(data),
        'dt': dt,
    }


def _add_motion_series(motion, kind, data, meta):
    if not data:
        return
    motion[kind] = data
    motion[kind + 'Meta'] = meta


def _merge_motion(motion, source):
    for kind in ('acceleration', 'velocity', 'displacement'):
        if kind in source:
            _add_motion_series(
                motion, kind, source[kind],
                source.get(kind + 'Meta', _series_meta(
                    source[kind], source.get('selectedPath', ''), kind)))


def _peer_or_tabular_wave_files(search_dir):
    peer_first = staticDynamicDB.first_peer_file_in_directory(search_dir)
    if peer_first:
        return [peer_first]
    files = []
    for filename in os.listdir(search_dir):
        lower = filename.lower()
        if (lower.endswith('.csv') or lower.endswith('.xlsx') or
                lower.endswith('.xls')):
            if 'vel' in lower or 'dis' in lower or 'acc' in lower:
                files.append(os.path.join(search_dir, filename))
    files.sort()
    return files


def load_wave_data(geo_type, file_path='', model_length_unit='m', report=None):
    search_files = []
    if file_path:
        if os.path.isdir(file_path):
            search_files.extend(_peer_or_tabular_wave_files(file_path))
        elif os.path.isfile(file_path):
            search_files.append(file_path)
        else:
            print('Warning: wave file not found: %s' %
                  _safe_log_text(file_path))

    if not search_files:
        search_dir = os.path.dirname(__file__) or '.'
        search_files.extend(_peer_or_tabular_wave_files(search_dir))

    motion = {
        'format': str(geo_type or '').upper(),
        'modelLengthUnit': model_length_unit,
    }
    for path in search_files:
        try:
            data = staticDynamicDB.read_wave_data(
                path, geo_type, model_length_unit)
        except Exception as e:
            print('Warning: Failed to read wave file "%s": %s' %
                  (_safe_log_text(path), _safe_log_text(e)))
            if report is not None:
                report.add_message(
                    'WARNING', 'Failed to read wave file "%s": %s' %
                    (_safe_log_text(path), _safe_log_text(e)))
            continue
        if isinstance(data, dict):
            _merge_motion(motion, data)
            for kind in ('acceleration', 'velocity', 'displacement'):
                if kind in data:
                    meta = data.get(kind + 'Meta', {})
                    print('Loaded PEER %s data: %s (%d points, %s -> model %s, scale %.6g)' %
                          (kind, _safe_log_text(meta.get('sourcePath', path)),
                           len(data[kind]), meta.get('sourceUnit', ''),
                           model_length_unit, float(meta.get('scale', 1.0))))
                    if report is not None:
                        report.add('Wave', kind + '.file',
                                   meta.get('sourcePath', path))
                        report.add('Wave', kind + '.points', len(data[kind]))
                        report.add('Wave', kind + '.source_unit',
                                   meta.get('sourceUnit', ''))
                        report.add('Wave', kind + '.scale',
                                   meta.get('scale', 1.0))
            continue

        if not data:
            continue
        kind = _wave_kind_from_filename(path)
        _add_motion_series(
            motion, kind, data,
            _series_meta(data, path, kind, 'model units', 1.0))
        print('Loaded %s data: %s (%d points)' %
              (kind, _safe_log_text(path), len(data)))
        if report is not None:
            report.add('Wave', kind + '.file', path)
            report.add('Wave', kind + '.points', len(data))

    if any([kind in motion for kind in ('acceleration', 'velocity',
                                        'displacement')]):
        if report is not None:
            report.add('Wave', 'model_length_unit', model_length_unit)
        return motion
    print('Warning: no valid wave data found; seismic load skipped.')
    if report is not None:
        report.add_message('WARNING', 'No valid wave data found; seismic load skipped.')
    return None


def _integrate_series(series):
    if not series:
        return []
    result = [(series[0][0], 0.0)]
    accum = 0.0
    prev_t, prev_v = series[0]
    for t, value in series[1:]:
        dt = float(t) - float(prev_t)
        accum += 0.5 * (float(prev_v) + float(value)) * dt
        result.append((t, accum))
        prev_t, prev_v = t, value
    return result


def _differentiate_series(series):
    if len(series) < 2:
        return []
    result = []
    for index, item in enumerate(series):
        if index == 0:
            t0, y0 = series[0]
            t1, y1 = series[1]
        elif index == len(series) - 1:
            t0, y0 = series[-2]
            t1, y1 = series[-1]
        else:
            t0, y0 = series[index - 1]
            t1, y1 = series[index + 1]
        dt = float(t1) - float(t0)
        value = 0.0 if abs(dt) <= 1.0e-20 else (float(y1) - float(y0)) / dt
        result.append((item[0], value))
    return result


def _prepare_motion_for_boundary_input(motion, report=None):
    prepared = dict(motion)
    if 'velocity' not in prepared:
        if 'acceleration' in prepared:
            prepared['velocity'] = _integrate_series(prepared['acceleration'])
            prepared['velocityMeta'] = {
                'sourcePath': 'integrated acceleration',
                'sourceUnit': 'model length/s',
                'scale': 1.0,
                'npts': len(prepared['velocity']),
                'dt': _series_meta(prepared['velocity'], '', 'velocity')['dt'],
            }
            if report is not None:
                report.add('Wave', 'velocity.generated',
                           'integrated acceleration')
        elif 'displacement' in prepared:
            prepared['velocity'] = _differentiate_series(
                prepared['displacement'])
            if report is not None:
                report.add('Wave', 'velocity.generated',
                           'differentiated displacement')

    if 'displacement' not in prepared:
        if 'velocity' in prepared:
            prepared['displacement'] = _integrate_series(prepared['velocity'])
            prepared['displacementMeta'] = {
                'sourcePath': 'integrated velocity',
                'sourceUnit': 'model length',
                'scale': 1.0,
                'npts': len(prepared['displacement']),
                'dt': _series_meta(
                    prepared['displacement'], '', 'displacement')['dt'],
            }
            if report is not None:
                report.add('Wave', 'displacement.generated',
                           'integrated velocity')

    if 'velocity' not in prepared or 'displacement' not in prepared:
        raise ValueError('Seismic input requires velocity and displacement data, or acceleration data that can be integrated.')
    return prepared


def _unit_vector(vector):
    vals = [float(item) for item in vector]
    mag = math.sqrt(sum([item * item for item in vals]))
    if mag <= 1.0e-20:
        return [0.0, 1.0, 0.0]
    return [item / mag for item in vals]


def _force_series(displacement, velocity, stiffness, dashpot, factor):
    count = min(len(displacement), len(velocity))
    data = []
    max_abs = 0.0
    for index in range(count):
        t = displacement[index][0]
        u = float(displacement[index][1])
        v = float(velocity[index][1])
        force = float(factor) * (float(stiffness) * u + float(dashpot) * v)
        if abs(force) > max_abs:
            max_abs = abs(force)
        data.append((t, force))
    return data, max_abs


def _series_time_increment(series):
    increments = []
    for index in range(1, len(series)):
        dt = float(series[index][0]) - float(series[index - 1][0])
        if dt > 1.0e-20:
            increments.append(dt)
    if not increments:
        return 0.0
    return min(increments)


def _delay_force_data(force_data, delay):
    delay = float(delay)
    if abs(delay) <= 1.0e-20:
        return force_data
    shifted = [(0.0, 0.0)]
    for t, value in force_data:
        shifted.append((float(t) + delay, value))
    return shifted


def _motion_delay_bin_size(delay_bin_size, displacement, velocity):
    try:
        bin_size = float(delay_bin_size)
    except Exception:
        bin_size = 0.0
    if bin_size <= 0.0:
        bin_size = max(_series_time_increment(displacement),
                       _series_time_increment(velocity))
    return bin_size


def _bin_arrival_delays(raw_delays, bin_size):
    delays = {}
    for label, raw_delay in raw_delays.items():
        delay = raw_delay
        if bin_size > 1.0e-20:
            delay = int(math.floor(raw_delay / bin_size + 0.5)) * bin_size
        delays[label] = delay

    if delays:
        min_delay = min(delays.values())
        if abs(min_delay) > 1.0e-20:
            delays = dict((label, delay - min_delay)
                          for label, delay in delays.items())
    unique_delays = sorted(set(['%.12g' % delay
                                for delay in delays.values()]))
    return delays, unique_delays


def _check_arrival_delay_bin_limit(unique_delays, mode_label, report=None):
    if len(unique_delays) <= MAX_TRAVELING_DELAY_BINS:
        return
    message = (
        '%s delay bins (%d) exceed the safety limit (%d). '
        'Increase Delay Bin Size or reduce the boundary mesh density.' %
        (mode_label, len(unique_delays), MAX_TRAVELING_DELAY_BINS))
    if report is not None:
        report.add_message('ERROR', message)
    raise ValueError(message)


def _add_face_arrival_delay_stats(boundary_faces, delays, report):
    if report is None:
        return
    for face_name in sorted(boundary_faces.keys()):
        face_delays = [
            delays.get(node.label, 0.0)
            for node in boundary_faces[face_name]
        ]
        if not face_delays:
            continue
        face_bins = sorted(set(['%.12g' % item for item in face_delays]))
        report.add('SeismicInput', face_name + '.arrival_delay_min',
                   min(face_delays))
        report.add('SeismicInput', face_name + '.arrival_delay_max',
                   max(face_delays))
        report.add('SeismicInput', face_name + '.arrival_delay_bins',
                   len(face_bins))


def _equivalent_node_vs(node, node_params=None, fallback_params=None):
    entries = []
    if node_params and node.label in node_params:
        entries = node_params[node.label]
        if isinstance(entries, dict):
            entries = [(entries, 1.0)]
    if not entries and fallback_params:
        entries = [(fallback_params, 1.0)]

    total_fraction = 0.0
    weighted_slowness = 0.0
    for params, fraction in entries:
        try:
            vs = float(params.get('Vs', 0.0))
            frac = float(fraction)
        except Exception:
            continue
        if vs <= 0.0 or frac <= 0.0:
            continue
        total_fraction += frac
        weighted_slowness += frac / vs
    if total_fraction <= 0.0 or weighted_slowness <= 0.0:
        return None
    return total_fraction / weighted_slowness


def _layered_site_profile_from_nodes(nodes, vertical_axis, node_params=None,
                                     fallback_params=None):
    axis = _axis_index(vertical_axis)
    samples = []
    for node in nodes:
        vs = _equivalent_node_vs(node, node_params, fallback_params)
        if vs is None or vs <= 0.0:
            continue
        samples.append((_node_coords(node)[axis], vs))

    if not samples:
        raise ValueError('LayeredSite input requires positive Vs values from model materials.')

    ordered = sorted(samples, key=lambda item: item[0])
    span = ordered[-1][0] - ordered[0][0]
    tol = max(1.0e-9, abs(span) * 1.0e-8)
    clusters = []
    for coord, vs in ordered:
        if not clusters or abs(coord - clusters[-1][-1][0]) > tol:
            clusters.append([(coord, vs)])
        else:
            clusters[-1].append((coord, vs))

    profile = []
    for cluster in clusters:
        coord = sum(item[0] for item in cluster) / float(len(cluster))
        slowness = sum(1.0 / item[1] for item in cluster)
        vs = float(len(cluster)) / slowness if slowness > 0.0 else 0.0
        profile.append({
            'coord': coord,
            'Vs': vs,
            'samples': len(cluster),
            'travelTime': 0.0,
        })

    travel_time = 0.0
    for index in range(1, len(profile)):
        prev = profile[index - 1]
        row = profile[index]
        dz = abs(row['coord'] - prev['coord'])
        travel_time += dz * 0.5 * (1.0 / prev['Vs'] + 1.0 / row['Vs'])
        row['travelTime'] = travel_time
    return profile


def _profile_time_at(coord, profile):
    if not profile:
        return 0.0
    if len(profile) == 1:
        return 0.0
    if coord <= profile[0]['coord']:
        return profile[0]['travelTime']
    if coord >= profile[-1]['coord']:
        return profile[-1]['travelTime']
    for index in range(1, len(profile)):
        prev = profile[index - 1]
        row = profile[index]
        if coord <= row['coord']:
            dz = row['coord'] - prev['coord']
            if abs(dz) <= 1.0e-20:
                return prev['travelTime']
            fraction = (coord - prev['coord']) / dz
            return prev['travelTime'] + \
                fraction * (row['travelTime'] - prev['travelTime'])
    return profile[-1]['travelTime']


def _node_layered_site_arrival_delays(boundary_faces, vertical_axis,
                                      node_params, fallback_params,
                                      delay_bin_size, displacement, velocity,
                                      report=None):
    nodes = _unique_nodes_from_faces(boundary_faces)
    if not nodes:
        return {}, {
            'mode': 'LayeredSite',
            'min_delay': 0.0,
            'max_delay': 0.0,
            'delay_bins': 0,
            'delay_bin_size': 0.0,
        }

    profile = _layered_site_profile_from_nodes(
        nodes, vertical_axis, node_params, fallback_params)
    axis = _axis_index(vertical_axis)
    raw_delays = dict(
        (node.label, _profile_time_at(_node_coords(node)[axis], profile))
        for node in nodes)
    bin_size = _motion_delay_bin_size(delay_bin_size, displacement, velocity)
    delays, unique_delays = _bin_arrival_delays(raw_delays, bin_size)
    _check_arrival_delay_bin_limit(
        unique_delays, 'LayeredSite arrival', report=report)

    vs_values = [row['Vs'] for row in profile]
    max_delay = max(delays.values()) if delays else 0.0
    stats = {
        'mode': 'LayeredSite',
        'min_delay': min(delays.values()) if delays else 0.0,
        'max_delay': max_delay,
        'delay_bins': len(unique_delays),
        'delay_bin_size': bin_size,
        'profile_points': len(profile),
        'site_travel_time': profile[-1]['travelTime'] if profile else 0.0,
        'site_vs_min': min(vs_values) if vs_values else 0.0,
        'site_vs_max': max(vs_values) if vs_values else 0.0,
    }
    if report is not None:
        report.add('SeismicInput', 'arrival_mode', 'LayeredSite')
        report.add('SeismicInput', 'site_profile_source',
                   'model_material_vs')
        report.add('SeismicInput', 'site_vertical_axis',
                   str(vertical_axis).upper())
        report.add('SeismicInput', 'site_profile_points',
                   stats['profile_points'])
        report.add('SeismicInput', 'site_travel_time',
                   stats['site_travel_time'])
        report.add('SeismicInput', 'site_vs_min', stats['site_vs_min'])
        report.add('SeismicInput', 'site_vs_max', stats['site_vs_max'])
        report.add('SeismicInput', 'arrival_delay_min',
                   stats['min_delay'])
        report.add('SeismicInput', 'arrival_delay_max',
                   stats['max_delay'])
        report.add('SeismicInput', 'arrival_delay_bins',
                   stats['delay_bins'])
        report.add('SeismicInput', 'arrival_delay_bin_size', bin_size)
        _add_face_arrival_delay_stats(boundary_faces, delays, report)
    export_seismic_site_profile_csv(profile, report=report)
    return delays, stats


def _node_arrival_delays(boundary_faces, propagation_vector,
                         apparent_velocity, delay_bin_size,
                         displacement, velocity, wave_input_mode,
                         node_params=None, fallback_params=None,
                         vertical_axis='Y', report=None):
    mode = normalize_wave_input_mode(wave_input_mode)
    if mode == 'LayeredSite':
        return _node_layered_site_arrival_delays(
            boundary_faces, vertical_axis, node_params, fallback_params,
            delay_bin_size, displacement, velocity, report=report)
    if mode != 'Traveling':
        return {}, {
            'mode': 'Uniform',
            'min_delay': 0.0,
            'max_delay': 0.0,
            'delay_bins': 1,
            'delay_bin_size': 0.0,
        }

    speed = float(apparent_velocity)
    if speed <= 0.0:
        raise ValueError('Traveling wave input requires Apparent Velocity greater than 0.')

    if _vector_magnitude(propagation_vector) <= 1.0e-20:
        raise ValueError('Traveling wave input requires a non-zero Propagation Vector.')

    nodes = _unique_nodes_from_faces(boundary_faces)
    if not nodes:
        return {}, {
            'mode': 'Traveling',
            'min_delay': 0.0,
            'max_delay': 0.0,
            'delay_bins': 0,
            'delay_bin_size': 0.0,
        }

    direction = _unit_vector(propagation_vector)
    projections = {}
    for node in nodes:
        coords = _node_coords(node)
        projections[node.label] = (
            coords[0] * direction[0] +
            coords[1] * direction[1] +
            coords[2] * direction[2])

    min_projection = min(projections.values())
    raw_delays = dict(
        (label, (projection - min_projection) / speed)
        for label, projection in projections.items())

    bin_size = _motion_delay_bin_size(delay_bin_size, displacement, velocity)
    delays, unique_delays = _bin_arrival_delays(raw_delays, bin_size)
    _check_arrival_delay_bin_limit(
        unique_delays, 'Traveling wave', report=report)

    max_delay = max(delays.values()) if delays else 0.0
    stats = {
        'mode': 'Traveling',
        'propagation_vector': direction,
        'apparent_velocity': speed,
        'min_delay': min(delays.values()) if delays else 0.0,
        'max_delay': max_delay,
        'delay_bins': len(unique_delays),
        'delay_bin_size': bin_size,
    }
    if report is not None:
        report.add('SeismicInput', 'arrival_mode', 'Traveling')
        report.add('SeismicInput', 'propagation_unit_vector', direction)
        report.add('SeismicInput', 'apparent_velocity', speed)
        report.add('SeismicInput', 'arrival_delay_min', stats['min_delay'])
        report.add('SeismicInput', 'arrival_delay_max', stats['max_delay'])
        report.add('SeismicInput', 'arrival_delay_bins', stats['delay_bins'])
        report.add('SeismicInput', 'arrival_delay_bin_size', bin_size)
        _add_face_arrival_delay_stats(boundary_faces, delays, report)
    return delays, stats


def _add_wave_direction_warnings(wave_type, incident_direction,
                                 propagation_direction, report=None):
    wtype = str(wave_type or '').strip().upper()
    if wtype not in ('P', 'S'):
        return
    dot = (
        incident_direction[0] * propagation_direction[0] +
        incident_direction[1] * propagation_direction[1] +
        incident_direction[2] * propagation_direction[2])
    abs_dot = abs(dot)
    message = None
    if wtype == 'P' and abs_dot < 0.5:
        message = ('P-wave input usually has motion direction close to the '
                   'propagation direction; check Incident Vector and '
                   'Propagation Vector.')
    if wtype == 'S' and abs_dot > 0.5:
        message = ('S-wave input usually has motion direction close to '
                   'perpendicular to the propagation direction; check '
                   'Incident Vector and Propagation Vector.')
    if report is not None:
        report.add('SeismicInput', 'incident_propagation_dot', dot)
    if message:
        print('Warning: ' + message)
        if report is not None:
            report.add_message('WARNING', message)


def _delete_prefixed_items(container, prefixes):
    for name in list(container.keys()):
        for prefix in prefixes:
            if name.startswith(prefix):
                del container[name]
                break


def setup_steps(model, function_option, step_name, step_type,
                t_time, d_time, iterations_num, save_num, report=None):
    previous = step_name if step_name in model.steps.keys() else 'Initial'
    analysis_step = 'Step-dynamic' if function_option == 'Seismic' else 'Step-static'
    if analysis_step in model.steps.keys():
        if report is not None:
            report.add('Analysis', 'final_step', analysis_step, 'existing')
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
    if report is not None:
        report.add('Analysis', 'final_step', analysis_step, 'created')
        report.add('Analysis', 'step_type', step_type)


def set_field_outputs(model, save_num):
    for request in model.fieldOutputRequests.values():
        request.setValues(frequency=int(save_num))


def apply_seismic_load(model, instance, boundary_faces, params, wave_data,
                       wave_type, theta, vertical_axis, model_dimension='3D',
                       node_params=None, wave_input_mode='Uniform',
                       propagation_vector=None, apparent_wave_velocity=0.0,
                       delay_bin_size=0.0, report=None):
    step_name = 'Step-dynamic'
    if step_name not in model.steps.keys():
        print('Warning: dynamic step not found; seismic load skipped.')
        if report is not None:
            report.add_message('WARNING', 'Dynamic step not found; seismic load skipped.')
        return

    motion = _prepare_motion_for_boundary_input(wave_data, report=report)
    displacement = motion['displacement']
    velocity = motion['velocity']
    direction = _unit_vector(theta)
    if propagation_vector is None:
        propagation_vector = _vertical_axis_vector(vertical_axis)
    arrival_delays, delay_stats = _node_arrival_delays(
        boundary_faces, propagation_vector, apparent_wave_velocity,
        delay_bin_size, displacement, velocity, wave_input_mode,
        node_params=node_params, fallback_params=params,
        vertical_axis=vertical_axis, report=report)
    if delay_stats.get('mode', 'Uniform') == 'LayeredSite':
        propagation_direction = _unit_vector(_vertical_axis_vector(
            vertical_axis))
    else:
        propagation_direction = _unit_vector(propagation_vector)
    if delay_stats.get('mode', 'Uniform') != 'Uniform':
        _add_wave_direction_warnings(
            wave_type, direction, propagation_direction, report=report)
        export_seismic_arrival_info_csv(
            instance, boundary_faces, arrival_delays, report=report)
    if report is not None:
        report.add('SeismicInput', 'direction_unit_vector', direction)
        report.add('SeismicInput', 'wave_type', wave_type)
        report.add('SeismicInput', 'input_mode',
                   delay_stats.get('mode', 'Uniform'))
        report.add('SeismicInput', 'points',
                   min(len(displacement), len(velocity)))

    assembly = model.rootAssembly
    _delete_prefixed_items(model.loads, ('SD_EQLoad_',))
    _delete_prefixed_items(model.amplitudes, ('SD_EQAmp_', 'SD_Wave_Amplitude'))
    _delete_prefixed_items(assembly.sets, ('SD_EQ_Group_',))

    active_dofs = (1, 2) if model_dimension == '2D' else (1, 2, 3)
    created_loads = 0
    skipped_zero = 0
    for face_name in sorted(boundary_faces.keys()):
        face_nodes = boundary_faces[face_name]
        if not face_nodes:
            continue
        normal_dof = _normal_dof_for_face(
            face_name, vertical_axis, model_dimension)
        if normal_dof not in active_dofs:
            continue
        shear_dofs = [d for d in active_dofs if d != normal_dof]
        specs = [('Normal', normal_dof, 'K_normal', 'C_normal')]
        if model_dimension == '2D':
            specs.append(('Shear', shear_dofs[0], 'K_shear', 'C_shear'))
        else:
            specs.append(('Shear1', shear_dofs[0], 'K_shear', 'C_shear'))
            specs.append(('Shear2', shear_dofs[1], 'K_shear', 'C_shear'))

        weights = _node_boundary_weights(
            face_nodes, face_name, vertical_axis, model_dimension)
        for comp_name, dof, stiffness_key, dashpot_key in specs:
            factor = direction[dof - 1]
            if abs(factor) <= 1.0e-12:
                continue
            grouped = {}
            for node in face_nodes:
                local_entries = [(params, 1.0)]
                if node_params and node.label in node_params:
                    local_entries = node_params[node.label]
                    if isinstance(local_entries, dict):
                        local_entries = [(local_entries, 1.0)]
                for local_params, material_fraction in local_entries:
                    influence = weights.get(node.label, 1.0) * material_fraction
                    stiffness = influence * local_params[stiffness_key]
                    dashpot = influence * local_params[dashpot_key]
                    material_name = local_params.get('material', 'Material')
                    delay = arrival_delays.get(node.label, 0.0)
                    key = ('%.12g' % stiffness, '%.12g' % dashpot,
                           material_name, '%.12g' % delay)
                    grouped.setdefault(key, []).append(node)

            for index, key in enumerate(sorted(grouped.keys()), 1):
                group_nodes = grouped[key]
                stiffness = float(key[0])
                dashpot = float(key[1])
                delay = float(key[3])
                force_data, max_force = _force_series(
                    displacement, velocity, stiffness, dashpot, factor)
                if max_force <= 1.0e-20:
                    skipped_zero += 1
                    continue
                force_data = _delay_force_data(force_data, delay)

                group_set = 'SD_EQ_Group_%s_%s_%03d' % (
                    face_name, comp_name, index)
                assembly.Set(
                    name=group_set,
                    nodes=_assembly_nodes_from_labels(instance, group_nodes))
                region = assembly.sets[group_set]

                amp_name = 'SD_EQAmp_%s_%s_%03d' % (
                    face_name, comp_name, index)
                model.TabularAmplitude(
                    name=amp_name, timeSpan=STEP, smooth=SOLVER_DEFAULT,
                    data=tuple(force_data))

                cf1 = 1.0 if dof == 1 else 0.0
                cf2 = 1.0 if dof == 2 else 0.0
                cf3 = 1.0 if dof == 3 else 0.0
                load_name = 'SD_EQLoad_%s_%s_%03d' % (
                    face_name, comp_name, index)
                model.ConcentratedForce(
                    name=load_name, createStepName=step_name,
                    region=region, cf1=cf1, cf2=cf2, cf3=cf3,
                    distributionType=UNIFORM, field='',
                    localCsys=None, amplitude=amp_name)
                created_loads += 1
                print('Created seismic equivalent load: %s DOF=%d nodes=%d delay=%.6g max|F|=%.6g' %
                      (load_name, dof, len(group_nodes), delay, max_force))

    print('Created seismic equivalent boundary loads: %d (skipped zero groups: %d).' %
          (created_loads, skipped_zero))
    if report is not None:
        report.add('SeismicInput', 'loads_created', created_loads)
        report.add('SeismicInput', 'zero_groups_skipped', skipped_zero)
    return {'loads_created': created_loads, 'zero_groups_skipped': skipped_zero}


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


def submit_job(model, job_name, cpu_num, gpu_num, auto_submit=False,
               report=None):
    job = create_analysis_job(
        model, job_name or model.name + '_StaticDynamic',
        cpu_num, gpu_num,
        'Static-Dynamic Analysis with Viscous-Spring Boundary',
        replace=True)
    print('Job "%s" created with %d CPUs, %d GPUs.' %
          (job.name, int(cpu_num), int(gpu_num)))
    if report is not None:
        report.add('Job', 'name', job.name)
        report.add('Job', 'cpu_num', int(cpu_num))
        report.add('Job', 'gpu_num', int(gpu_num))
        report.add('Job', 'auto_submit', auto_submit)
    if auto_submit:
        job.submit(consistencyChecking=OFF)
        print('Job "%s" submitted.' % job.name)
        job.waitForCompletion()
        print('Job "%s" finished with status: %s' %
              (job.name, mdb.jobs[job.name].status))
        if report is not None:
            report.add('Job', 'status', mdb.jobs[job.name].status)
