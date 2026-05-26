# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

from abaqus import mdb


PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

import StaticDynamic


CASES = [
    {
        'model': 'SD_Test_3D_Homogeneous_Soil',
        'part': 'soil',
        'instance': 'soil-1',
        'soil_set': 'Set-soil',
        'vertical_axis': 'Z',
        'expected_dimension': '3D',
        'expected_faces': 5,
        'expected_unique_nodes': 273,
        'expected_weight_totals': {
            'Bottom': 1600.0,
            'XMin': 1200.0,
            'XMax': 1200.0,
            'YMin': 1200.0,
            'YMax': 1200.0,
        },
    },
    {
        'model': 'SD_Validate_Layered_3D',
        'part': 'soil',
        'instance': 'soil-1',
        'soil_set': 'Set-soil',
        'vertical_axis': 'Z',
        'expected_dimension': '3D',
        'expected_faces': 5,
    },
    {
        'model': 'SD_Validate_Layered_3D_1m',
        'part': 'soil',
        'instance': 'soil-1',
        'soil_set': 'Set-soil',
        'vertical_axis': 'Z',
        'expected_dimension': '3D',
        'expected_faces': 5,
    },
]


def _close_enough(actual, expected):
    tolerance = max(1.0e-6, abs(expected) * 1.0e-6)
    return abs(actual - expected) <= tolerance


def _validate_case(case):
    model_name = case['model']
    if model_name not in mdb.models.keys():
        print('SKIP %s: model not found in current Abaqus session.' %
              model_name)
        return True

    model = mdb.models[model_name]
    assembly = model.rootAssembly
    instance_name = case['instance']
    if instance_name not in assembly.instances.keys():
        print('FAIL %s: instance "%s" not found.' %
              (model_name, instance_name))
        return False

    instance = assembly.instances[instance_name]
    dimension = StaticDynamic.get_model_dimension(
        model, case['part'], instance)
    if dimension != case.get('expected_dimension'):
        print('FAIL %s: dimension %s, expected %s.' %
              (model_name, dimension, case.get('expected_dimension')))
        return False

    faces = StaticDynamic.get_boundary_node_faces(
        model, instance, case.get('soil_set', ''),
        case.get('vertical_axis', 'Y'), dimension)
    active_faces = [name for name in faces.keys() if faces[name]]
    expected_faces = case.get('expected_faces')
    if expected_faces is not None and len(active_faces) != expected_faces:
        print('FAIL %s: active faces %d, expected %d.' %
              (model_name, len(active_faces), expected_faces))
        return False

    unique_nodes = StaticDynamic._unique_nodes_from_faces(faces)
    expected_unique_nodes = case.get('expected_unique_nodes')
    if (expected_unique_nodes is not None and
            len(unique_nodes) != expected_unique_nodes):
        print('FAIL %s: unique boundary nodes %d, expected %d.' %
              (model_name, len(unique_nodes), expected_unique_nodes))
        return False

    expected_weight_totals = case.get('expected_weight_totals', {})
    for face_name in sorted(faces.keys()):
        weights = StaticDynamic._node_boundary_weights(
            faces[face_name], face_name,
            case.get('vertical_axis', 'Y'), dimension)
        total = sum(weights.values()) if weights else 0.0
        print('  %s.%s total_weight=%.6g nodes=%d' %
              (model_name, face_name, total, len(faces[face_name])))
        if face_name in expected_weight_totals:
            expected = expected_weight_totals[face_name]
            if not _close_enough(total, expected):
                print('FAIL %s: %s weight %.6g, expected %.6g.' %
                      (model_name, face_name, total, expected))
                return False

    print('PASS %s' % model_name)
    return True


def main():
    passed = True
    for case in CASES:
        passed = _validate_case(case) and passed
    if not passed:
        raise RuntimeError('StaticDynamic validation failed.')
    print('StaticDynamic current-session validation complete.')


if __name__ == '__main__':
    main()
