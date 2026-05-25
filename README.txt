环境安装说明
必须使用 Python 3.9.13，其他版本可能导致课程代码无法运行。


============================================================
第一步：安装 Python 3.9.13
============================================================

Windows：

  双击本目录下的 python-3.9.13-amd64.exe
  安装时勾选 "Add Python to PATH"，其余默认下一步

macOS：

  下载安装包（复制链接到浏览器打开）：
  https://www.python.org/ftp/python/3.9.13/python-3.9.13-macos11.pkg
  下载后双击安装，一路默认即可

安装完成后确认版本（命令行输入）：
  Windows：  py -3.9 --version
  macOS：    python3.9 --version
  应显示：Python 3.9.13


============================================================
第二步：安装依赖 & 启动 Notebook（一键脚本）
============================================================

Windows：

  双击运行 setup.bat
  （若弹出安全提示，选择"仍要运行"）
  脚本自动安装所有依赖包，完成后浏览器自动打开 Jupyter Notebook

macOS：

  打开终端，cd 进入本文件夹，例如：
    cd "/Users/你的用户名/AI 培训/setup"
  赋予权限并运行：
    chmod +x setup.sh && ./setup.sh
  脚本自动安装所有依赖包，完成后浏览器自动打开 Jupyter Notebook

torch 包较大，安装过程请耐心等待。


============================================================
手动安装（脚本无法运行时）
============================================================

Windows：

1. 按 Win+R，输入 cmd，回车打开命令提示符
2. 进入本文件夹（把路径改成实际路径）：
   cd /d "C:\你的路径\setup"
3. 安装依赖：
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
4. 启动 Jupyter Notebook：
   py -3.9 -m jupyter notebook

macOS：

1. 打开终端，进入本文件夹：
   cd "/你的路径/setup"
2. 安装依赖：
   pip3.9 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
3. 启动 Jupyter Notebook：
   python3.9 -m jupyter notebook


============================================================
文件说明
============================================================

setup.bat                Windows 一键脚本（安装依赖 + 启动 Notebook）
setup.sh                 macOS 一键脚本（安装依赖 + 启动 Notebook）
python-3.9.13-amd64.exe  Windows Python 安装包
requirements.txt         课程依赖列表
