// The Pharmacy Drawer launchers. build.py compiles this once per launcher, choosing
// the mode with a /define. Each finds Python 3.10+ with Tcl/Tk and SQLite, as
// docs/RUNNING.md describes, and starts the application from the app folder.
// Any arguments given to a launcher are passed on to the application.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;

[assembly: AssemblyTitle(Launcher.Name)]
[assembly: AssemblyProduct("EPICS Pharmacy Drawer")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

static class Launcher
{
#if BROWSER
    public const string Name = "Browser Cabinet";
    const string Module = "pharm.web";
    static readonly string[] Options = { "--open-browser" };
    const bool Visible = true;  // the console runs the local web server; closing it stops the server
#elif USB
    public const string Name = "USB Bench";
    const string Module = "pharm.app";
    static readonly string[] Options = { "--usb" };
    const bool Visible = true;  // the console shows hardware diagnostics
#elif TEAM_USB
    public const string Name = "Team USB Bench";
    const string Module = "pharm.app";
    static readonly string[] Options = { "--team-usb" };
    const bool Visible = true;
#else
    public const string Name = "Pharmacy Drawer";
    const string Module = "pharm.app";
    static readonly string[] Options = { };
    const bool Visible = false;  // the desktop app in simulation, with no console window
#endif

    const string Check = "import sys, tkinter, sqlite3; assert sys.version_info >= (3, 10); tkinter.Tcl()";
    const int ControlCExit = unchecked((int)0xC000013A);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int MessageBoxW(IntPtr owner, string text, string caption, uint type);

    [DllImport("user32.dll")]
    static extern bool SetProcessDPIAware();

    [STAThread]
    static int Main(string[] args)
    {
        string app = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "app");
        if (!File.Exists(Path.Combine(app, Path.Combine("pharm", "app.py"))))
            return Fail("The app folder is missing.\n\nKeep " + Name + ".exe in the same folder as its app folder.");

        string python = FindPython(app);
        if (python == null)
        {
            SetProcessDPIAware();
            if (MessageBoxW(IntPtr.Zero, "Python 3.10 or later with Tcl/Tk is required.\n\nInstall Python from python.org, "
                    + "then open " + Name + " again.\n\nOpen python.org now?", Name, 0x10 | 0x4) == 6)
                Process.Start("https://www.python.org/downloads/");
            return 1;
        }
        if (Module == "pharm.web" && Run(python, app, "-B -c \"import pharm, flask\"") != 0)
            return Fail("The browser cabinet needs Flask, which app\\runtime-dependencies.zip supplies.\n\n"
                + "Restore that file, or install app\\requirements.txt with your Python.");

        var arguments = new List<string> { "-B", "-m", Module };
        arguments.AddRange(Options);
        arguments.AddRange(args);
        string command = Join(arguments);

        if (!Visible)
        {
            string windowless = Windowless(python);
            if (windowless != null)
            {
                Start(windowless, app, command, false);
                return 0;
            }
        }
        if (Visible)
        {
            Console.Title = Name;
            Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e) { e.Cancel = true; };
        }
        using (Process process = Start(python, app, command, !Visible))
        {
            process.WaitForExit();
            int code = process.ExitCode;
            if (code == 0 || code == ControlCExit)
                return 0;
            if (!Visible)
                return Fail(Name + " stopped with an error.\n\nSee app\\docs\\RUNNING.md, and application.log in "
                    + "%LOCALAPPDATA%\\EPICS-Pharm.");
            Console.WriteLine();
            Console.WriteLine(Name + " stopped with an error. See the message above and app\\docs\\RUNNING.md.");
            Console.WriteLine("Press any key to close this window.");
            Console.ReadKey(true);
            return code;
        }
    }

    // The same interpreters as before, in the same order: a project .venv, this
    // computer's bundled runtime, then the Python launcher and Pythons on PATH.
    static string FindPython(string app)
    {
        var candidates = new List<string>
        {
            Path.Combine(app, @".venv\Scripts\python.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                @".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        };
        foreach (string name in new[] { "py.exe", "python.exe", "python3.exe" })
            candidates.AddRange(OnPath(name));
        var tried = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (string candidate in candidates)
            if (tried.Add(candidate) && File.Exists(candidate) && Run(candidate, app, "-B -c \"" + Check + "\"") == 0)
                return candidate;
        return null;
    }

    static IEnumerable<string> OnPath(string name)
    {
        foreach (string entry in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            string directory = Environment.ExpandEnvironmentVariables(entry.Trim().Trim('"'));
            if (directory.Length == 0 || directory.IndexOfAny(Path.GetInvalidPathChars()) >= 0)
                continue;
            yield return Path.Combine(directory, name);
        }
    }

    static string Windowless(string python)
    {
        string name = Path.GetFileName(python).Equals("py.exe", StringComparison.OrdinalIgnoreCase) ? "pyw.exe" : "pythonw.exe";
        string path = Path.Combine(Path.GetDirectoryName(python), name);
        return File.Exists(path) ? path : null;
    }

    static int Run(string exe, string directory, string arguments)
    {
        try
        {
            using (Process process = Start(exe, directory, arguments, true))
            {
                if (process.WaitForExit(60000))
                    return process.ExitCode;
                try { process.Kill(); } catch (InvalidOperationException) { } catch (Win32Exception) { }
                return -1;
            }
        }
        catch (Win32Exception) { return -1; }
        catch (InvalidOperationException) { return -1; }
    }

    static Process Start(string exe, string directory, string arguments, bool hidden)
    {
        return Process.Start(new ProcessStartInfo(exe, arguments)
        {
            WorkingDirectory = directory,
            UseShellExecute = false,
            CreateNoWindow = hidden,
        });
    }

    static int Fail(string message)
    {
        SetProcessDPIAware();
        MessageBoxW(IntPtr.Zero, message, Name, 0x10);
        return 1;
    }

    // Quote arguments the way the C runtime reads them back.
    static string Join(IEnumerable<string> arguments)
    {
        var line = new StringBuilder();
        foreach (string argument in arguments)
        {
            if (line.Length > 0)
                line.Append(' ');
            if (argument.Length > 0 && argument.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
            {
                line.Append(argument);
                continue;
            }
            line.Append('"');
            int slashes = 0;
            foreach (char c in argument)
            {
                if (c == '\\') { slashes++; continue; }
                line.Append('\\', c == '"' ? slashes * 2 + 1 : slashes).Append(c);
                slashes = 0;
            }
            line.Append('\\', slashes * 2).Append('"');
        }
        return line.ToString();
    }
}
