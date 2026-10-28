// Generic askpass client. The credential exists only in its same-user session pipe.
using System;
using System.IO;
using System.IO.Pipes;
class TT10SessionAuth {
  static int Main(string[] args) {
    try {
      using(var pipe=new NamedPipeClientStream(".","PatientQwenTT10Window02Auth",PipeDirection.In)) {
        pipe.Connect(3000);
        using(var reader=new StreamReader(pipe)) {
          string secret=reader.ReadLine();
          if(String.IsNullOrEmpty(secret))return 2;
          Console.Out.WriteLine(secret);Console.Out.Flush();secret=null;
        }
      }
      return 0;
    } catch { return 2; }
  }
}
