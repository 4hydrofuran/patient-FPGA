using System;
using System.Windows.Forms;
using System.Drawing;
class TT10AskPass {
  [STAThread] static int Main(string[] args) {
    Application.EnableVisualStyles();
    using (Form f=new Form()) {
      f.Text="KV260 TT10-00 隐藏认证";f.ClientSize=new Size(450,140);
      f.StartPosition=FormStartPosition.CenterScreen;f.FormBorderStyle=FormBorderStyle.FixedDialog;
      f.MaximizeBox=false;f.MinimizeBox=false;f.TopMost=true;
      Label l=new Label();l.Text="固定板端 ubuntu 认证；凭据仅在内存传递，不写入日志。";
      l.SetBounds(15,15,425,38);f.Controls.Add(l);
      TextBox p=new TextBox();p.UseSystemPasswordChar=true;p.SetBounds(15,59,420,25);f.Controls.Add(p);
      Button ok=new Button();ok.Text="认证";ok.SetBounds(250,100,85,27);ok.DialogResult=DialogResult.OK;f.Controls.Add(ok);
      Button cancel=new Button();cancel.Text="取消";cancel.SetBounds(345,100,85,27);cancel.DialogResult=DialogResult.Cancel;f.Controls.Add(cancel);
      f.AcceptButton=ok;f.CancelButton=cancel;f.Shown+=(s,e)=>p.Focus();
      if(f.ShowDialog()!=DialogResult.OK||p.Text.Length==0)return 2;
      Console.Out.WriteLine(p.Text);Console.Out.Flush();p.Clear();return 0;
    }
  }
}
