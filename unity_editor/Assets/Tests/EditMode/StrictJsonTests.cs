using Neram.Core;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace Neram.Tests
{
    /// <summary>The replay parser must accept exactly what Python's json.loads accepts (RFC 8259 + NaN/Infinity).</summary>
    [TestFixture]
    public class StrictJsonTests
    {
        private static readonly string[] Accepted =
        {
            "{\"a\":1}", "{\"a\":-0.5e-3}", "{\"a\":[1,2,{\"b\":null}]}", " {\"a\" : true } ", "{\"a\":\"\\u00b0C \\\"q\\\" \\n\"}",
            "{\"a\":NaN}", "{\"a\":Infinity}", "{\"a\":-Infinity}", "{\"a\":1e400}", "{}", "[]", "{\"a\":\"2026-10-08T00:00:00Z\"}",
        };

        private static readonly string[] Rejected =
        {
            "{'a':1}", "{a:1}", "{\"a\":'x'}", "{\"a\":1,}", "[1,2,]", "{\"a\":0x1F}", "{\"a\":01}", "{\"a\":.5}", "{\"a\":1.}",
            "{\"a\":+1}", "{\"a\":undefined}", "{\"a\":new Date(1)}", "{\"a\":1} /*c*/", "{\"a\":1} x", "{\"a\":\"\\x41\"}",
            "{\"a\":\"tab\there\"}", "{\"a\":tru}", "{\"a\":1", "", "{\"a\":-}", "{\"a\":1e}", "{\"a\":nan}",
        };

        [Test]
        public void AcceptsStandardJsonAndPythonConstants()
        {
            foreach (var s in Accepted)
                Assert.DoesNotThrow(() => StrictJson.Parse(s), s);
        }

        [Test]
        public void RejectsEverythingPythonRejects()
        {
            foreach (var s in Rejected)
                Assert.Throws<JsonReaderException>(() => StrictJson.Parse(s), s);
        }

        [Test]
        public void TimestampsStayStringsAndDuplicateKeysFail()
        {
            var o = (JObject)StrictJson.Parse("{\"created_utc\":\"2026-10-08T00:00:00Z\"}");
            Assert.AreEqual(JTokenType.String, o["created_utc"].Type);
            Assert.Throws<JsonReaderException>(() => StrictJson.Parse("{\"a\":1,\"a\":2}"));
        }
    }
}
