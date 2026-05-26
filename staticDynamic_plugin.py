# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

from abaqusGui import *
from abaqusConstants import ALL

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from staticDynamic_Form import StaticDynamicForm


toolset = getAFXApp().getAFXMainWindow().getPluginToolset()
icon_path = os.path.join(plugin_dir, 'icons', 'icon1.png')
try:
    icon = afxCreatePNGIcon(icon_path)
except Exception:
    icon = None
toolset.registerGuiMenuButton(
    buttonText='StaticDynamic v0.2.1',
    object=StaticDynamicForm(toolset),
    messageId=AFXMode.ID_ACTIVATE,
    icon=icon,
    kernelInitString='import os, sys; p=r"%s"; sys.path.insert(0, p) if p not in sys.path else None; import StaticDynamic' % plugin_dir,
    applicableModules=ALL,
    version='0.2.1',
    author='YANG',
    description='Static-dynamic analysis with visual viscous-spring boundary')
