using System;
using System.Linq;
using System.Reflection;

// Minimal NUnit runner (reflection) so the Unity EditMode tests also run in CI without Unity.
public static class Runner
{
    public static int Main(string[] args)
    {
        var asm = typeof(Runner).Assembly;
        int pass = 0, fail = 0, ignored = 0;
        var filter = args.Length > 0 ? args[0] : null;
        foreach (var type in asm.GetTypes().Where(t => t.GetMethods().Any(m => m.GetCustomAttributes().Any(a => a.GetType().Name == "TestAttribute"))).OrderBy(t => t.Name))
        {
            var setup = type.GetMethods().FirstOrDefault(m => m.GetCustomAttributes().Any(a => a.GetType().Name == "SetUpAttribute"));
            foreach (var m in type.GetMethods().Where(m => m.GetCustomAttributes().Any(a => a.GetType().Name == "TestAttribute")).OrderBy(m => m.Name))
            {
                var name = type.Name + "." + m.Name;
                if (filter != null && !name.Contains(filter)) continue;
                var inst = Activator.CreateInstance(type);
                try
                {
                    setup?.Invoke(inst, null);
                    m.Invoke(inst, null);
                    pass++;
                    Console.WriteLine("  PASS " + name);
                }
                catch (TargetInvocationException ex)
                {
                    var inner = ex.InnerException;
                    if (inner != null && inner.GetType().Name == "IgnoreException") { ignored++; Console.WriteLine("  IGNORED " + name + ": " + inner.Message); continue; }
                    fail++;
                    Console.WriteLine("  FAIL " + name + ": " + inner?.GetType().Name + ": " + inner?.Message);
                    if (inner != null && inner.GetType().Name != "AssertionException") Console.WriteLine(inner.StackTrace);
                }
            }
        }
        Console.WriteLine($"\n{pass} passed, {fail} failed, {ignored} ignored");
        return fail == 0 ? 0 : 1;
    }
}
