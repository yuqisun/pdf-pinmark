"""pytest 共享 fixture 与沙箱兼容补丁。

DSH 沙箱会拒绝枚举以 mode=0o700 创建的目录（os.listdir/scandir 报
PermissionError），而 pytest 9 的 tmp_path 恰好用 mode=0o700 建临时目录。
此补丁让 Path.mkdir 忽略 mode 参数（Windows 下 mode 本就无效果），使
tmp_path 在沙箱与普通环境都可用。对非沙箱 Linux 环境，临时目录改用默认
权限，属可接受的测试安全放宽。
"""

import pathlib

_orig_mkdir = pathlib.Path.mkdir


def _mkdir(self, mode=0o777, parents=False, exist_ok=False):
    # 故意忽略 mode，规避沙箱对 0o700 目录的限制
    return _orig_mkdir(self, parents=parents, exist_ok=exist_ok)


pathlib.Path.mkdir = _mkdir
