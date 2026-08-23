#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oneT GUI 无控制台入口

Windows 下双击 .pyw 文件由 pythonw.exe 运行，不创建 cmd 黑窗。
命令行调试请用 main.py（python main.py）。
"""

import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from main import main

if __name__ == "__main__":
    main()
