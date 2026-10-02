# X128 首轮 native 编译失败记录

首次执行 `run_b02_x128.ps1 -Target native` 时，冻结 B01 编译和 43 笔基线测试通过；随后候选编译命令返回退出码 1。终端错误为：

```text
g++.exe: fatal error: cannot execute 'D:/mingw64/bin/../libexec/gcc/x86_64-w64-mingw32/16.2.0/cc1plus.exe': CreateProcess: No such file or directory
compilation terminated.
native_compile failed: 1
```

随后确认 `cc1plus.exe` 文件存在，原命令重试通过，候选数值测试、Csim、综合和 Cosim 均成功。首次运行脚本会覆盖同名 `logs/b02/x128/native_compile.log` 和收据，故原始失败文件未保存；本说明据当次终端输出整理，不冒充原始工具日志。该失败发生在本机编译器子进程启动阶段，没有被计为核设计失败。
