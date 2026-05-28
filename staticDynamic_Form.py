# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import traceback

from abaqusGui import *
from staticDynamicDB import StaticDynamicDB, StaticDynamicDBFileHandler


_ID_BASE = 2000
ID_FILE_BROWSE = _ID_BASE + 24
ID_NODE_SET_CHK = _ID_BASE + 30
ID_NODE_INFO_CHK = _ID_BASE + 31
ID_SPRING_DAMP_CHK = _ID_BASE + 32
ID_SEISMIC_CHK = _ID_BASE + 33
ID_AUTO_SUBMIT_CHK = _ID_BASE + 34
ID_GEOSTATIC_FILE_BROWSE = _ID_BASE + 35
ID_GEOSTATIC_SOURCE = _ID_BASE + 36

GEOSTATIC_ODB_PATTERNS = 'ODB Files (*.odb);;All Files (*)'
GEOSTATIC_CSV_PATTERNS = 'CSV Files (*.csv);;All Files (*)'
GEOSTATIC_ALL_PATTERNS = (
    'Geostatic Files (*.odb, *.csv);;ODB Files (*.odb);;'
    'CSV Files (*.csv);;All Files (*)')


def _debug_log(message):
    if str(os.environ.get('STATICDYNAMIC_DEBUG', '')).lower() not in (
            '1', 'true', 'yes', 'on'):
        return
    path = os.path.join(os.path.dirname(__file__), 'dialog_debug.log')
    f = open(path, 'a')
    f.write(str(message) + '\n')
    f.close()


def _geostatic_source_patterns(source):
    if str(source or '').upper() == 'CSV':
        return GEOSTATIC_CSV_PATTERNS
    if str(source or '').upper() == 'ODB':
        return GEOSTATIC_ODB_PATTERNS
    return GEOSTATIC_ALL_PATTERNS


def _geostatic_extension_matches(source, path):
    lower = str(path or '').lower()
    if str(source or '').upper() == 'CSV':
        return lower.endswith('.csv')
    if str(source or '').upper() == 'ODB':
        return lower.endswith('.odb')
    return True


def _nonzero_vector_text(text, allow_empty=True):
    raw = str(text or '').strip()
    if not raw:
        return allow_empty
    try:
        vals = [float(item.strip()) for item in raw.split(',')]
        if len(vals) != 3:
            return False
        return sum([item * item for item in vals]) > 1.0e-20
    except Exception:
        return False


class StaticDynamicForm(AFXForm):
    def __init__(self, owner):
        AFXForm.__init__(self, owner)
        self.cmd = AFXGuiCommand(self, 'Main', 'StaticDynamic', True)
        self.Model_nameKw = AFXStringKeyword(self.cmd, 'Model_name', True, 'Model-1')
        self.soilInstance_nameKw = AFXStringKeyword(self.cmd, 'soilInstance_name', True, 'soil-1')
        self.soilPart_nameKw = AFXStringKeyword(self.cmd, 'soilPart_name', True, 'soil')
        self.soilSetKw = AFXStringKeyword(self.cmd, 'soilSet', True, 'Set-soil')
        self.depthKw = AFXFloatKeyword(self.cmd, 'depth', True, 0.0)
        self.verticalAxisKw = AFXStringKeyword(self.cmd, 'verticalAxis', True, 'Y')
        self.geoTypeKw = AFXStringKeyword(self.cmd, 'geoType', True, 'PEER')
        self.modelLengthUnitKw = AFXStringKeyword(self.cmd, 'modelLengthUnit', True, 'm')
        self.geostaticFileTypeKw = AFXStringKeyword(self.cmd, 'geostaticFileType', True, 'ODB')
        self.geostaticFileKw = AFXStringKeyword(self.cmd, 'geostaticFile', True, '')
        self.balanceToleranceKw = AFXFloatKeyword(self.cmd, 'balanceTolerance', True, 1.0e-4)
        self.functionOptionKw = AFXStringKeyword(self.cmd, 'functionOption', True, 'Seismic')
        self.stepTypeKw = AFXStringKeyword(self.cmd, 'stepType', True, 'Implicit')
        self.stepNameKw = AFXStringKeyword(self.cmd, 'stepName', True, 'Step-geo')
        self.wave111Kw = AFXStringKeyword(self.cmd, 'wave111', True, 'P')
        self.theta_aKw = AFXStringKeyword(self.cmd, 'theta_a', True, '0,1,0')
        self.waveInputModeKw = AFXStringKeyword(self.cmd, 'waveInputMode', True, 'Uniform')
        self.propagationVectorKw = AFXStringKeyword(self.cmd, 'propagationVector', True, '')
        self.apparentWaveVelocityKw = AFXFloatKeyword(self.cmd, 'apparentWaveVelocity', True, 0.0)
        self.delayBinSizeKw = AFXFloatKeyword(self.cmd, 'delayBinSize', True, 0.0)
        self.t_timeKw = AFXFloatKeyword(self.cmd, 't_time', True, 20.0)
        self.d_timeKw = AFXFloatKeyword(self.cmd, 'd_time', True, 0.01)
        self.iterationsNumKw = AFXIntKeyword(self.cmd, 'iterationsNum', True, 20)
        self.saveNumKw = AFXIntKeyword(self.cmd, 'saveNum', True, 2)
        self.cpuNumKw = AFXIntKeyword(self.cmd, 'cpuNum', True, 4)
        self.gpuNumKw = AFXIntKeyword(self.cmd, 'gpuNum', True, 0)
        self.initialJobNameKw = AFXStringKeyword(self.cmd, 'initialJobName', True, '')
        self.NodeSetKw = AFXBoolKeyword(self.cmd, 'NodeSet', True, True)
        self.NodeInfoKw = AFXBoolKeyword(self.cmd, 'NodeInfo', True, False)
        self.SpringDampingKw = AFXBoolKeyword(self.cmd, 'SpringDamping', True, False)
        self.SeismicLoadKw = AFXBoolKeyword(self.cmd, 'SeismicLoad', True, False)
        self.autoSubmitKw = AFXBoolKeyword(self.cmd, 'autoSubmit', True, False)
        self.fileNameKw = AFXStringKeyword(self.cmd, 'fileName', True, '')

    def getFirstDialog(self):
        return StaticDynamicDialog(self)

    def doCustomChecks(self):
        spring = self.SpringDampingKw.getValue()
        seismic = self.SeismicLoadKw.getValue()
        node_set = self.NodeSetKw.getValue()

        def _err(msg):
            print('ERROR: ' + msg.replace('\n', ' '))
            try:
                showAFXErrorDialog(self.getFirstDialog(), msg)
            except Exception:
                pass

        if spring and not node_set:
            _err('Spring Damping requires Node Set Establishment.')
            return False
        if seismic and not spring:
            _err('Seismic Load requires Spring Damping.')
            return False
        if seismic and not node_set:
            _err('Seismic Load requires Node Set Establishment.')
            return False
        if seismic and self.functionOptionKw.getValue() != 'Seismic':
            _err('Seismic Load requires Function Option = Seismic.')
            return False
        if seismic and not _nonzero_vector_text(self.theta_aKw.getValue(),
                                                allow_empty=False):
            _err('Incident Vector must be a non-zero x,y,z vector.')
            return False
        if seismic and self.waveInputModeKw.getValue() == 'Traveling':
            if self.apparentWaveVelocityKw.getValue() <= 0.0:
                _err('Traveling wave input requires Apparent Velocity greater than 0.')
                return False
            if not _nonzero_vector_text(self.propagationVectorKw.getValue()):
                _err('Propagation Vector must be a non-zero x,y,z vector.')
                return False
        if seismic and self.delayBinSizeKw.getValue() < 0.0:
            _err('Delay Bin Size cannot be negative.')
            return False
        geostatic_file = self.geostaticFileKw.getValue()
        if spring and (not geostatic_file or not os.path.isfile(geostatic_file)):
            _err('Spring Damping requires a valid geostatic ODB or CSV file.')
            return False
        if spring and self.depthKw.getValue() <= 0.0:
            _err('Spring Damping requires Structure Depth greater than 0.')
            return False
        if spring and self.balanceToleranceKw.getValue() <= 0.0:
            _err('Spring Damping requires Balance Tol greater than 0.')
            return False
        source = self.geostaticFileTypeKw.getValue()
        if spring and geostatic_file and not _geostatic_extension_matches(
                source, geostatic_file):
            _err('The selected geostatic file extension does not match the Geostatic Source.')
            return False
        return True


class StaticDynamicDialog(AFXDataDialog):
    def __init__(self, owner):
        _debug_log('StaticDynamicDialog.__init__ start')
        try:
            self._build(owner)
            _debug_log('StaticDynamicDialog.__init__ complete')
        except Exception:
            _debug_log(traceback.format_exc())
            raise

    def _build(self, owner):
        AFXDataDialog.__init__(self, owner, 'Static-Dynamic Analysis',
                               self.OK | self.CANCEL,
                               DIALOG_ACTIONS_SEPARATOR | DIALOG_NORMAL,
                               0, 0, 720, 700)
        self.owner = owner
        self.db = StaticDynamicDB(self)
        form = owner

        main_frame = FXVerticalFrame(self, FRAME_RAISED | LAYOUT_FILL_X | LAYOUT_FILL_Y)
        content = FXHorizontalFrame(main_frame, LAYOUT_FILL_X | LAYOUT_FILL_Y)

        tab1 = FXVerticalFrame(content, FRAME_RAISED | LAYOUT_FILL_X | LAYOUT_FILL_Y)
        FXLabel(tab1, 'Model Parameters', None)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Model Name:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.modelNameTxt = AFXTextField(row, 20, '', form.Model_nameKw, 0,
                                         AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.modelNameTxt.setText('Model-1')

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Soil Instance:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.soilInstanceTxt = AFXTextField(row, 20, '', form.soilInstance_nameKw, 0,
                                            AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.soilInstanceTxt.setText('soil-1')

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Soil Part:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.soilPartTxt = AFXTextField(row, 20, '', form.soilPart_nameKw, 0,
                                        AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.soilPartTxt.setText('soil')

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Soil Set:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.soilSetTxt = AFXTextField(row, 20, '', form.soilSetKw, 0,
                                       AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.soilSetTxt.setText('Set-soil')

        FXHorizontalSeparator(tab1, SEPARATOR_GROOVE | LAYOUT_FILL_X)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Structure Depth:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.depthSpin = AFXFloatSpinner(row, 10, '', form.depthKw, 0)
        self.depthSpin.setRange(0.0, 1.0e6)
        self.depthSpin.setValue(0.0)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Vertical Axis:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.verticalAxisCmb = AFXComboBox(row, 10, 2, '', form.verticalAxisKw, 0,
                                           LAYOUT_FILL_X)
        self.verticalAxisCmb.appendItem('X')
        self.verticalAxisCmb.appendItem('Y')
        self.verticalAxisCmb.appendItem('Z')
        self.verticalAxisCmb.setCurrentItem(1)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Geostatic Source:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.geostaticSourceCmb = AFXComboBox(
            row, 10, 2, '', form.geostaticFileTypeKw,
            ID_GEOSTATIC_SOURCE, LAYOUT_FILL_X)
        self.geostaticSourceCmb.appendItem('ODB')
        self.geostaticSourceCmb.appendItem('CSV')
        self.geostaticSourceCmb.setCurrentItem(0)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Geostatic File:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.geostaticFileTxt = AFXTextField(row, 24, '', form.geostaticFileKw, 0,
                                             AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.geostaticFileBtn = FXButton(row, 'Browse...', None, self,
                                         ID_GEOSTATIC_FILE_BROWSE,
                                         BUTTON_NORMAL | LAYOUT_CENTER_Y)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Balance Tol:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.balanceTolSpin = AFXFloatSpinner(row, 10, '', form.balanceToleranceKw, 0)
        self.balanceTolSpin.setRange(0.0, 1.0e3)
        self.balanceTolSpin.setValue(1.0e-4)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Wave Format:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.geoTypeCmb = AFXComboBox(row, 10, 2, '', form.geoTypeKw, 0,
                                      LAYOUT_FILL_X)
        self.geoTypeCmb.appendItem('PEER')
        self.geoTypeCmb.appendItem('CSV')
        self.geoTypeCmb.appendItem('Excel')
        self.geoTypeCmb.setCurrentItem(0)

        FXHorizontalSeparator(tab1, SEPARATOR_GROOVE | LAYOUT_FILL_X)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'CPU Num:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.cpuSpin = AFXSpinner(row, 8, '', form.cpuNumKw, 0)
        self.cpuSpin.setRange(1, 128)
        self.cpuSpin.setValue(4)
        FXLabel(row, 'GPU Num:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y)
        self.gpuSpin = AFXSpinner(row, 8, '', form.gpuNumKw, 0)
        self.gpuSpin.setRange(0, 16)
        self.gpuSpin.setValue(0)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Initial Job Name:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.jobTxt = AFXTextField(row, 20, '', form.initialJobNameKw, 0,
                                   AFXTEXTFIELD_STRING | LAYOUT_FILL_X)

        row = FXHorizontalFrame(tab1, LAYOUT_FILL_X)
        FXLabel(row, 'Wave File:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 115, 0)
        self.fileTxt = AFXTextField(row, 24, '', form.fileNameKw, 0,
                                    AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.fileBtn = FXButton(row, 'Browse...', None, self,
                                ID_FILE_BROWSE, BUTTON_NORMAL | LAYOUT_CENTER_Y)

        tab2 = FXVerticalFrame(content, FRAME_RAISED | LAYOUT_FILL_X | LAYOUT_FILL_Y)
        FXLabel(tab2, 'Analysis Parameters', None)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Function Option:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.funcOptionCmb = AFXComboBox(row, 10, 2, '', form.functionOptionKw, 0,
                                         LAYOUT_FILL_X)
        self.funcOptionCmb.appendItem('Seismic')
        self.funcOptionCmb.appendItem('Static')
        self.funcOptionCmb.setCurrentItem(0)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Step Type:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.stepTypeCmb = AFXComboBox(row, 10, 2, '', form.stepTypeKw, 0,
                                       LAYOUT_FILL_X)
        self.stepTypeCmb.appendItem('Implicit')
        self.stepTypeCmb.appendItem('Explicit')
        self.stepTypeCmb.setCurrentItem(0)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Geostatic Step Name:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.stepNameTxt = AFXTextField(row, 20, '', form.stepNameKw, 0,
                                        AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.stepNameTxt.setText('Step-geo')

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Waveform:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.waveCmb = AFXComboBox(row, 10, 2, '', form.wave111Kw, 0,
                                   LAYOUT_FILL_X)
        self.waveCmb.appendItem('P')
        self.waveCmb.appendItem('S')
        self.waveCmb.setCurrentItem(0)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Incident Vector:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.thetaTxt = AFXTextField(row, 20, '', form.theta_aKw, 0,
                                     AFXTEXTFIELD_STRING | LAYOUT_FILL_X)
        self.thetaTxt.setText('0,1,0')

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Input Mode:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.waveInputModeCmb = AFXComboBox(
            row, 10, 2, '', form.waveInputModeKw, 0, LAYOUT_FILL_X)
        self.waveInputModeCmb.appendItem('Uniform')
        self.waveInputModeCmb.appendItem('Traveling')
        self.waveInputModeCmb.setCurrentItem(0)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Propagation Vector:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.propagationTxt = AFXTextField(
            row, 20, '', form.propagationVectorKw, 0,
            AFXTEXTFIELD_STRING | LAYOUT_FILL_X)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Apparent Velocity:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.apparentVelocitySpin = AFXFloatSpinner(
            row, 10, '', form.apparentWaveVelocityKw, 0)
        self.apparentVelocitySpin.setRange(0.0, 1.0e12)
        self.apparentVelocitySpin.setValue(0.0)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Delay Bin Size:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.delayBinSpin = AFXFloatSpinner(
            row, 10, '', form.delayBinSizeKw, 0)
        self.delayBinSpin.setRange(0.0, 1.0e6)
        self.delayBinSpin.setValue(0.0)

        row = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(row, 'Model Length Unit:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.modelLengthUnitCmb = AFXComboBox(
            row, 10, 2, '', form.modelLengthUnitKw, 0, LAYOUT_FILL_X)
        self.modelLengthUnitCmb.appendItem('m')
        self.modelLengthUnitCmb.appendItem('cm')
        self.modelLengthUnitCmb.appendItem('mm')
        self.modelLengthUnitCmb.setCurrentItem(0)

        FXHorizontalSeparator(tab2, SEPARATOR_GROOVE | LAYOUT_FILL_X)

        hf1 = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(hf1, 'Time Period:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.tTimeSpin = AFXFloatSpinner(hf1, 10, '', form.t_timeKw, 0)
        self.tTimeSpin.setRange(0.0, 1.0e6)
        self.tTimeSpin.setValue(20.0)

        hf2 = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(hf2, 'Increment Size:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.dTimeSpin = AFXFloatSpinner(hf2, 10, '', form.d_timeKw, 0)
        self.dTimeSpin.setRange(1.0e-6, 1.0e6)
        self.dTimeSpin.setValue(0.01)

        hf3 = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(hf3, 'Iteration Number:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.iterSpin = AFXSpinner(hf3, 10, '', form.iterationsNumKw, 0)
        self.iterSpin.setRange(1, 1000)
        self.iterSpin.setValue(20)

        hf4 = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        FXLabel(hf4, 'Save Number:', None, JUSTIFY_LEFT | LAYOUT_CENTER_Y, 0, 0, 130, 0)
        self.saveSpin = AFXSpinner(hf4, 10, '', form.saveNumKw, 0)
        self.saveSpin.setRange(1, 1000)
        self.saveSpin.setValue(2)

        FXHorizontalSeparator(tab2, SEPARATOR_GROOVE | LAYOUT_FILL_X)
        FXLabel(tab2, 'Functions:', None)
        chk_row1 = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        self.nodeSetChk = FXCheckButton(chk_row1, 'Node Set Establishment', self, ID_NODE_SET_CHK)
        self.nodeSetChk.setCheck(True)
        self.nodeInfoChk = FXCheckButton(chk_row1, 'Node Information', self, ID_NODE_INFO_CHK)
        chk_row2 = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        self.springDampChk = FXCheckButton(chk_row2, 'Spring Damping', self, ID_SPRING_DAMP_CHK)
        self.seismicChk = FXCheckButton(chk_row2, 'Seismic Load', self, ID_SEISMIC_CHK)
        chk_row3 = FXHorizontalFrame(tab2, LAYOUT_FILL_X)
        self.autoSubmitChk = FXCheckButton(chk_row3, 'Auto Submit Final Job', self, ID_AUTO_SUBMIT_CHK)

        FXMAPFUNC(self, SEL_COMMAND, ID_FILE_BROWSE, self.onBrowseFile)
        FXMAPFUNC(self, SEL_COMMAND, ID_GEOSTATIC_FILE_BROWSE, self.onBrowseGeostaticFile)
        FXMAPFUNC(self, SEL_COMMAND, ID_GEOSTATIC_SOURCE, self.onGeostaticSource)
        FXMAPFUNC(self, SEL_COMMAND, ID_NODE_SET_CHK, self.onNodeSetChk)
        FXMAPFUNC(self, SEL_COMMAND, ID_NODE_INFO_CHK, self.onNodeInfoChk)
        FXMAPFUNC(self, SEL_COMMAND, ID_SPRING_DAMP_CHK, self.onSpringDampChk)
        FXMAPFUNC(self, SEL_COMMAND, ID_SEISMIC_CHK, self.onSeismicChk)
        FXMAPFUNC(self, SEL_COMMAND, ID_AUTO_SUBMIT_CHK, self.onAutoSubmitChk)

        self.fileHandler = StaticDynamicDBFileHandler(
            self, self.fileTxt, self.fileBtn, self.fileTxt,
            dbKey='fileName')
        self.geostaticFileHandler = StaticDynamicDBFileHandler(
            self, self.geostaticFileTxt, self.geostaticFileBtn,
            self.geostaticFileTxt, fileKeyword=form.geostaticFileKw,
            title='Select Geostatic File',
            patterns=GEOSTATIC_ODB_PATTERNS, dbKey='geostaticFile')
        self._sync_geostatic_file_patterns()
        FXHorizontalSeparator(self, SEPARATOR_GROOVE | LAYOUT_FILL_X)
        self._update_option_states()

    def onBrowseFile(self, sender, sel, ptr, data=None):
        self.fileHandler.activate()

    def onBrowseGeostaticFile(self, sender, sel, ptr, data=None):
        self.geostaticFileHandler.activate()

    def onGeostaticSource(self, sender, sel, ptr, data=None):
        self.owner.geostaticFileTypeKw.setValue(
            self.geostaticSourceCmb.getText())
        self._sync_geostatic_file_patterns()
        self._update_option_states()

    def _sync_geostatic_file_patterns(self):
        source = self.geostaticSourceCmb.getText()
        self.geostaticFileHandler.setPatterns(
            _geostatic_source_patterns(source))

    def _is_checked(self, widget):
        try:
            return bool(widget.getCheck())
        except Exception:
            try:
                return bool(widget.isChecked())
            except Exception:
                return False

    def onNodeSetChk(self, sender, sel, ptr, data=None):
        checked = self._is_checked(self.nodeSetChk)
        self.owner.NodeSetKw.setValue(checked)
        if not checked:
            self.nodeInfoChk.setCheck(False)
            self.owner.NodeInfoKw.setValue(False)
            self.springDampChk.setCheck(False)
            self.owner.SpringDampingKw.setValue(False)
            self.seismicChk.setCheck(False)
            self.owner.SeismicLoadKw.setValue(False)
        self._update_option_states()

    def onNodeInfoChk(self, sender, sel, ptr, data=None):
        checked = self._is_checked(self.nodeInfoChk)
        self.owner.NodeInfoKw.setValue(checked)
        if checked:
            self.nodeSetChk.setCheck(True)
            self.owner.NodeSetKw.setValue(True)
        self._update_option_states()

    def onSpringDampChk(self, sender, sel, ptr, data=None):
        checked = self._is_checked(self.springDampChk)
        self.owner.SpringDampingKw.setValue(checked)
        if checked:
            self.nodeSetChk.setCheck(True)
            self.owner.NodeSetKw.setValue(True)
        else:
            self.seismicChk.setCheck(False)
            self.owner.SeismicLoadKw.setValue(False)
        self._update_option_states()

    def onSeismicChk(self, sender, sel, ptr, data=None):
        checked = self._is_checked(self.seismicChk)
        self.owner.SeismicLoadKw.setValue(checked)
        if checked:
            self.nodeSetChk.setCheck(True)
            self.owner.NodeSetKw.setValue(True)
            self.springDampChk.setCheck(True)
            self.owner.SpringDampingKw.setValue(True)
        self._update_option_states()

    def onAutoSubmitChk(self, sender, sel, ptr, data=None):
        self.owner.autoSubmitKw.setValue(self._is_checked(self.autoSubmitChk))

    def _set_enabled(self, widgets, enabled):
        for widget in widgets:
            try:
                if enabled:
                    widget.enable()
                else:
                    widget.disable()
            except Exception:
                pass

    def _update_option_states(self):
        node_set = self._is_checked(self.nodeSetChk)
        spring = self._is_checked(self.springDampChk)
        seismic = self._is_checked(self.seismicChk)

        self._set_enabled([self.nodeInfoChk, self.springDampChk], node_set)
        self._set_enabled([self.seismicChk], node_set and spring)

        geostatic_widgets = [
            self.geostaticSourceCmb,
            self.geostaticFileTxt,
            self.geostaticFileBtn,
            self.balanceTolSpin,
            self.stepNameTxt,
        ]
        dynamic_widgets = [
            self.funcOptionCmb,
            self.stepTypeCmb,
            self.waveCmb,
            self.thetaTxt,
            self.waveInputModeCmb,
            self.propagationTxt,
            self.apparentVelocitySpin,
            self.delayBinSpin,
            self.modelLengthUnitCmb,
            self.tTimeSpin,
            self.dTimeSpin,
            self.iterSpin,
            self.saveSpin,
            self.cpuSpin,
            self.gpuSpin,
            self.jobTxt,
            self.geoTypeCmb,
            self.fileTxt,
            self.fileBtn,
        ]
        self._set_enabled(geostatic_widgets, spring)
        self._set_enabled(dynamic_widgets, seismic)
        self._set_enabled([self.autoSubmitChk], seismic)
        if not seismic:
            self.autoSubmitChk.setCheck(False)
            self.owner.autoSubmitKw.setValue(False)

    def processUpdates(self):
        pass
