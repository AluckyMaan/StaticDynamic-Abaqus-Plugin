# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import os

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
            'geostaticFileType': form.geostaticSourceCmb.getText(),
            'geostaticFile': form.geostaticFileTxt.getText(),
            'balanceTolerance': form.balanceTolSpin.getValue(),
            'stepType': form.stepTypeCmb.getText(),
            'stepName': form.stepNameTxt.getText(),
            'wave111': form.waveCmb.getText(),
            'theta_a': form.thetaTxt.getText(),
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
                 patterns=None):
        self.form = form
        self.fileTextField = fileTextField
        self.fileButton = fileButton
        self.patternTarget = patternTarget
        self.fileKeyword = fileKeyword
        self.title = title
        self.fileName = ''
        self.patterns = patterns or (
            'Wave Files (*.csv, *.xlsx);;CSV Files (*.csv);;'
            'Excel Files (*.xlsx);;All Files (*)')

    def activate(self):
        from abaqusGui import AFXFileSelectorDialog, AFXSELECTFILE_EXISTING

        file_kw = self.fileKeyword or self.form.owner.fileNameKw
        dialog = AFXFileSelectorDialog(
            self.form, self.title, file_kw, None,
            AFXSELECTFILE_EXISTING)
        dialog.setReadOnlyPatterns(self.patterns)
        dialog.create()
        dialog.showModal()
        self.fileName = file_kw.getValue()
        if self.fileName:
            self.fileTextField.setText(self.fileName)


def read_csv_file(path):
    if not os.path.isfile(path):
        raise StaticDynamicFileNotFoundError(path)
    rows = []
    f = open(path, 'rb')
    try:
        for row in csv.reader(f):
            rows.append(row)
    finally:
        f.close()
    return rows


def read_csv_data(filepath):
    data = []
    f = open(filepath, 'r')
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


def read_wave_data(filepath, geo_type='CSV'):
    if not os.path.exists(filepath):
        raise StaticDynamicFileNotFoundError(filepath)

    lower = filepath.lower()
    if geo_type.upper() == 'CSV' or lower.endswith('.csv'):
        return read_csv_data(filepath)
    return read_excel_data(filepath)
