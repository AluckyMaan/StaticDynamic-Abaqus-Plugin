# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import os
import re
import sys

try:
    import xlrd
except ImportError:
    xlrd = None

try:
    import xlwt
except ImportError:
    xlwt = None


class StaticDynamicFileNotFoundError(Exception):
    pass


PEER_GRAVITY = 9.80665
PEER_EXTENSIONS = {
    '.at2': 'acceleration',
    '.vt2': 'velocity',
    '.dt2': 'displacement',
}


def _open_csv_read(path):
    if sys.version_info[0] >= 3:
        return open(path, 'r', newline='')
    return open(path, 'rb')


class StaticDynamicDB(object):
    def __init__(self, form):
        self.form = form
        self._data = {}

    def getValue(self, kw):
        return self._data.get(kw, None)

    def setValue(self, kw, value):
        self._data[kw] = value

    def _is_checked(self, widget):
        try:
            return bool(widget.getCheck())
        except Exception:
            try:
                return bool(widget.isChecked())
            except Exception:
                return False

    def processUpdates(self):
        form = self.form
        data = {
            'functionOption': form.funcOptionCmb.getText(),
            'Model_name': form.modelNameTxt.getText(),
            'soilInstance_name': form.soilInstanceTxt.getText(),
            'soilPart_name': form.soilPartTxt.getText(),
            'soilSet': form.soilSetTxt.getText(),
            'depth': form.depthSpin.getValue(),
            'verticalAxis': form.verticalAxisCmb.getText(),
            'geoType': form.geoTypeCmb.getText(),
            'modelLengthUnit': form.modelLengthUnitCmb.getText(),
            'geostaticFileType': form.geostaticSourceCmb.getText(),
            'geostaticFile': form.geostaticFileTxt.getText(),
            'balanceTolerance': form.balanceTolSpin.getValue(),
            'stepType': form.stepTypeCmb.getText(),
            'stepName': form.stepNameTxt.getText(),
            'wave111': form.waveCmb.getText(),
            'theta_a': form.thetaTxt.getText(),
            'waveInputMode': form.waveInputModeCmb.getText(),
            'propagationVector': form.propagationTxt.getText(),
            'incidentAngle': form.incidentAngleSpin.getValue(),
            'azimuthAngle': form.azimuthAngleSpin.getValue(),
            'apparentWaveVelocity': form.apparentVelocitySpin.getValue(),
            'delayBinSize': form.delayBinSpin.getValue(),
            'siteProfileFile': form.siteProfileTxt.getText(),
            'waveScale': form.waveScaleSpin.getValue(),
            'baselineCorrection': form.baselineCorrectionCmb.getText(),
            't_time': form.tTimeSpin.getValue(),
            'd_time': form.dTimeSpin.getValue(),
            'iterationsNum': form.iterSpin.getValue(),
            'saveNum': form.saveSpin.getValue(),
            'cpuNum': form.cpuSpin.getValue(),
            'gpuNum': form.gpuSpin.getValue(),
            'initialJobName': form.jobTxt.getText(),
            'fileName': form.fileTxt.getText(),
            'NodeSet': self._is_checked(form.nodeSetChk),
            'NodeInfo': self._is_checked(form.nodeInfoChk),
            'SpringDamping': self._is_checked(form.springDampChk),
            'SeismicLoad': self._is_checked(form.seismicChk),
            'autoSubmit': self._is_checked(form.autoSubmitChk),
        }
        self._data.update(data)


class StaticDynamicDBFileHandler(object):
    def __init__(self, form, fileTextField, fileButton, patternTarget,
                 fileKeyword=None, title='Select Wave File',
                 patterns=None, dbKey=None):
        self.form = form
        self.fileTextField = fileTextField
        self.fileButton = fileButton
        self.patternTarget = patternTarget
        self.fileKeyword = fileKeyword
        self.title = title
        self.dbKey = dbKey
        self.fileName = ''
        self.patterns = patterns or (
            'Wave Files (*.at2, *.vt2, *.dt2, *.csv, *.xlsx);;'
            'PEER Files (*.at2, *.vt2, *.dt2);;CSV Files (*.csv);;'
            'Excel Files (*.xlsx);;All Files (*)')

    def setPatterns(self, patterns):
        self.patterns = patterns

    def activate(self):
        from abaqusGui import AFXFileSelectorDialog, AFXSELECTFILE_EXISTING

        file_kw = self.fileKeyword or self.form.owner.fileNameKw
        dialog = AFXFileSelectorDialog(
            self.form, self.title, file_kw, None,
            AFXSELECTFILE_EXISTING)
        dialog.setReadOnlyPatterns(self.patterns)
        dialog.create()
        if dialog.showModal():
            self.fileName = file_kw.getValue()
            if self.fileName:
                self.fileTextField.setText(self.fileName)
                try:
                    file_kw.setValue(self.fileName)
                except Exception:
                    pass
                if self.dbKey:
                    self.form.db.setValue(self.dbKey, self.fileName)


def read_csv_file(path):
    if not os.path.isfile(path):
        raise StaticDynamicFileNotFoundError(path)
    rows = []
    f = _open_csv_read(path)
    try:
        for row in csv.reader(f):
            rows.append(row)
    finally:
        f.close()
    return rows


def read_csv_data(filepath):
    data = []
    f = _open_csv_read(filepath)
    try:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                data.append((float(row[0]), float(row[1])))
            except (ValueError, TypeError):
                continue
    finally:
        f.close()
    return data


def read_excel_data(filepath, sheet_name=None):
    if xlrd is None:
        raise ImportError('xlrd library is required for Excel support')

    wb = xlrd.open_workbook(filepath)
    if sheet_name is None:
        sheet = wb.sheet_by_index(0)
    else:
        sheet = wb.sheet_by_name(sheet_name)

    data = []
    for row_idx in range(sheet.nrows):
        if sheet.ncols < 2:
            continue
        try:
            t = float(sheet.cell_value(row_idx, 0))
            v = float(sheet.cell_value(row_idx, 1))
            data.append((t, v))
        except (ValueError, TypeError):
            continue
    return data


def _model_length_unit_scale(model_length_unit):
    unit = str(model_length_unit or 'm').strip().lower()
    if unit in ('m', 'meter', 'meters', 'metre', 'metres'):
        return 1.0
    if unit in ('cm', 'centimeter', 'centimeters', 'centimetre', 'centimetres'):
        return 100.0
    if unit in ('mm', 'millimeter', 'millimeters', 'millimetre', 'millimetres'):
        return 1000.0
    raise ValueError('Unsupported model length unit: %s' % model_length_unit)


def _peer_unit_scale(kind, unit_text, model_length_unit):
    meter_to_model = _model_length_unit_scale(model_length_unit)
    text = str(unit_text or '').upper()
    if kind == 'acceleration':
        if 'UNITS OF G' in text or text.endswith(' G') or ' OF G' in text:
            return PEER_GRAVITY * meter_to_model
        if 'CM/S/S' in text or 'CM/SEC/SEC' in text or 'CM/S^2' in text:
            return 0.01 * meter_to_model
        if 'M/S/S' in text or 'M/SEC/SEC' in text or 'M/S^2' in text:
            return meter_to_model
    if kind == 'velocity':
        if 'CM/S' in text or 'CM/SEC' in text:
            return 0.01 * meter_to_model
        if 'M/S' in text or 'M/SEC' in text:
            return meter_to_model
    if kind == 'displacement':
        if 'CM' in text:
            return 0.01 * meter_to_model
        if 'M' in text:
            return meter_to_model
    return 1.0


def _peer_header_value(pattern, text, default=None):
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return default
    return match.group(1)


def read_peer_file(filepath, model_length_unit='m'):
    if not os.path.isfile(filepath):
        raise StaticDynamicFileNotFoundError(filepath)

    ext = os.path.splitext(filepath)[1].lower()
    kind = PEER_EXTENSIONS.get(ext)
    if kind is None:
        raise ValueError('Unsupported PEER extension: %s' % ext)

    f = open(filepath, 'r')
    try:
        lines = f.readlines()
    finally:
        f.close()

    if len(lines) < 4:
        raise ValueError('PEER file is too short: %s' % filepath)

    unit_text = lines[2].strip()
    header = lines[3]
    npts = int(_peer_header_value(r'NPTS\s*=\s*([0-9]+)', header, 0))
    dt = float(_peer_header_value(
        r'DT\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)',
        header, 0.0))
    if npts <= 0 or dt <= 0.0:
        raise ValueError('Could not parse NPTS/DT from PEER file: %s' %
                         filepath)

    values = []
    for line in lines[4:]:
        for token in line.replace(',', ' ').split():
            try:
                values.append(float(token))
            except Exception:
                pass

    if len(values) < npts:
        raise ValueError('PEER file has %d values, expected %d: %s' %
                         (len(values), npts, filepath))
    if len(values) > npts:
        values = values[:npts]

    scale = _peer_unit_scale(kind, unit_text, model_length_unit)
    data = []
    for index, value in enumerate(values):
        data.append((index * dt, value * scale))

    return {
        'kind': kind,
        'data': data,
        'npts': npts,
        'dt': dt,
        'sourceUnit': unit_text,
        'scale': scale,
        'sourcePath': filepath,
        'modelLengthUnit': model_length_unit,
    }


def peer_companion_files(filepath):
    directory = os.path.dirname(filepath)
    stem = os.path.splitext(os.path.basename(filepath))[0]
    companions = {}
    for ext, kind in PEER_EXTENSIONS.items():
        path = os.path.join(directory, stem + ext.upper())
        if not os.path.isfile(path):
            path = os.path.join(directory, stem + ext.lower())
        if os.path.isfile(path):
            companions[kind] = path
    return companions


def first_peer_file_in_directory(directory):
    if not os.path.isdir(directory):
        return None
    candidates = []
    for filename in os.listdir(directory):
        if os.path.splitext(filename)[1].lower() in PEER_EXTENSIONS:
            candidates.append(filename)
    if not candidates:
        return None
    candidates.sort()
    return os.path.join(directory, candidates[0])


def read_peer_motion(filepath, model_length_unit='m'):
    if os.path.isdir(filepath):
        first_file = first_peer_file_in_directory(filepath)
        if first_file is None:
            raise StaticDynamicFileNotFoundError(filepath)
        filepath = first_file

    companions = peer_companion_files(filepath)
    if not companions:
        companions = {
            PEER_EXTENSIONS.get(os.path.splitext(filepath)[1].lower()): filepath
        }

    motion = {
        'format': 'PEER',
        'selectedPath': filepath,
        'modelLengthUnit': model_length_unit,
    }
    for kind, path in sorted(companions.items()):
        if kind is None:
            continue
        record = read_peer_file(path, model_length_unit)
        motion[kind] = record['data']
        motion[kind + 'Meta'] = record
    return motion


def is_peer_wave_path(filepath):
    if os.path.isdir(filepath):
        return first_peer_file_in_directory(filepath) is not None
    return os.path.splitext(filepath)[1].lower() in PEER_EXTENSIONS


def read_wave_data(filepath, geo_type='CSV', model_length_unit='m'):
    if not os.path.exists(filepath):
        raise StaticDynamicFileNotFoundError(filepath)

    geo_text = str(geo_type or '').upper()
    lower = filepath.lower()
    if geo_text == 'PEER' or is_peer_wave_path(filepath):
        return read_peer_motion(filepath, model_length_unit)
    if geo_text == 'CSV' or lower.endswith('.csv'):
        return read_csv_data(filepath)
    return read_excel_data(filepath)
