using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Neram.Unity;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEditor.SceneManagement;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>
    /// File-based request queue so routine editor jobs (refresh, CAD placement, evidence renders, plan renders R01-R07, validation, EditMode
    /// tests, player build) can be triggered without clicking menus. Drop an empty "&lt;job&gt;.req" file into
    /// &lt;workspace&gt;/_automation/; the result is written to "&lt;job&gt;.txt" next to it. Editor-only, no effect on the player.
    /// </summary>
    [InitializeOnLoad]
    public static class NeramAutomation
    {
        public static readonly string Dir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "_automation"));
        private static double _next;
        private static bool _busy;

        static NeramAutomation()
        {
            Directory.CreateDirectory(Dir);
            EditorApplication.update += Tick;
            CompilationPipeline.assemblyCompilationFinished += (asm, msgs) =>
            {
                var errs = msgs.Where(m => m.type == CompilerMessageType.Error).Select(m => m.file + "(" + m.line + "): " + m.message).ToList();
                try { File.AppendAllText(Path.Combine(Dir, "compile.txt"), DateTime.Now.ToString("HH:mm:ss") + " " + Path.GetFileName(asm) + ": " + (errs.Count == 0 ? "OK" : string.Join("\n  ", errs)) + "\n"); }
                catch { /* best effort */ }
            };
            Write("status.txt", "loaded " + DateTime.Now.ToString("u"));
        }

        private static void Write(string file, string text)
        {
            try { File.WriteAllText(Path.Combine(Dir, file), text); } catch { /* best effort */ }
        }

        private static bool Take(string job)
        {
            var p = Path.Combine(Dir, job + ".req");
            if (!File.Exists(p)) return false;
            try { File.Delete(p); } catch { return false; }
            return true;
        }

        private static void Tick()
        {
            if (_busy || EditorApplication.timeSinceStartup < _next) return;
            _next = EditorApplication.timeSinceStartup + 1.0;
            if (EditorApplication.isCompiling || EditorApplication.isUpdating || EditorApplication.isPlayingOrWillChangePlaymode) return;
            _busy = true;
            try
            {
                if (Take("refresh")) { AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport); Write("refresh.txt", "refreshed " + DateTime.Now.ToString("u")); }
                if (Take("place")) Place();
                if (Take("snap")) Write("snap.txt", NeramCadSnapshots.RenderViews(Path.Combine(Dir, "views.txt"), Path.Combine(Dir, "snaps")));
                if (Take("renders")) Write("renders.txt", NeramRenders.RenderAll());
                if (Take("extras")) Write("extras.txt", NeramSceneExtras.Apply());
                if (Take("look")) Write("look.txt", NeramLook.Apply());
                if (Take("diag")) Write("diag.txt", Neram.EditorTools.NeramDiag.Run());
                if (Take("validate")) { bool ok = NeramValidation.Run(out var rep); Write("validate.txt", (ok ? "PASSED\n" : "FAILED\n") + rep); }
                if (Take("tests")) RunTests();
                if (Take("build")) { var r = NeramBuild.BuildWindows(); Write("build.txt", (r.ok ? "OK " : "FAIL ") + r.message); }
            }
            catch (Exception ex) { Write("error.txt", DateTime.Now.ToString("u") + "\n" + ex); }
            finally { _busy = false; }
        }

        private static void Place()
        {
            var scene = EditorSceneManager.GetActiveScene();
            if (scene.path != NeramSetup.ScenePath) scene = EditorSceneManager.OpenScene(NeramSetup.ScenePath);
            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) { Write("place.txt", "NERAM_Assembly not found"); return; }
            var log = NeramCadPlacement.PlaceAll(asm.transform, out int n);
            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);
            Write("place.txt", n + " placed\n" + log);
        }

        private static void RunTests()
        {
            var api = ScriptableObject.CreateInstance<TestRunnerApi>();
            api.RegisterCallbacks(new Cb());
            api.Execute(new ExecutionSettings(new Filter { testMode = TestMode.EditMode }));
        }

        private sealed class Cb : ICallbacks
        {
            public void RunStarted(ITestAdaptor t) => Write("tests.txt", "running " + DateTime.Now.ToString("u"));
            public void TestStarted(ITestAdaptor t) { }
            public void TestFinished(ITestResultAdaptor r) { }
            public void RunFinished(ITestResultAdaptor r)
            {
                var sb = new StringBuilder();
                sb.AppendLine("pass " + r.PassCount + " fail " + r.FailCount + " skip " + r.SkipCount + " inconclusive " + r.InconclusiveCount);
                void Walk(ITestResultAdaptor x)
                {
                    if (!x.HasChildren && x.TestStatus == TestStatus.Failed) sb.AppendLine("FAIL " + x.FullName + "\n  " + x.Message);
                    if (x.HasChildren) foreach (var c in x.Children) Walk(c);
                }
                Walk(r);
                Write("tests.txt", sb.ToString());
            }
        }
    }
}
