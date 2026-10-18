using System;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Neram.Core
{
    /// <summary>
    /// Strict single-value JSON parsing for replay lines, matching Python's json.loads exactly.
    ///
    /// Newtonsoft.Json is lenient: it accepts single quotes, unquoted keys, trailing commas, hex and leading-zero
    /// numbers, "undefined", constructors and comments, and turns ISO timestamps into Date tokens. A replay that
    /// Python rejects must never be shown by Unity, so every line is first checked against the RFC 8259 grammar by
    /// <see cref="CheckSyntax"/>. The only extension accepted is the one Python accepts (NaN, Infinity, -Infinity);
    /// those are then rejected per field with E011, as in Python.
    /// </summary>
    public static class StrictJson
    {
        private static readonly JsonLoadSettings Load = new JsonLoadSettings
        {
            DuplicatePropertyNameHandling = DuplicatePropertyNameHandling.Error,
            CommentHandling = CommentHandling.Ignore,
            LineInfoHandling = LineInfoHandling.Ignore,
        };

        /// <summary>Parse one JSON value. Throws JsonReaderException on any syntax error or duplicate key.</summary>
        public static JToken Parse(string text)
        {
            CheckSyntax(text);
            try { return ReadToken(text); }
            catch (JsonReaderException)
            {
                // The syntax is already valid RFC 8259. Newtonsoft (Mono double parsing) rejects numbers outside the
                // double range such as 1e400, which Python's json.loads reads as +/-inf. Do the same, then retry; the
                // non-finite value is rejected per field (E011) exactly as in Python. (Sai, 18 Oct 2026)
                string normalised = NormaliseOverflow(text);
                if (ReferenceEquals(normalised, text)) throw;
                return ReadToken(normalised);
            }
        }

        private static JToken ReadToken(string text)
        {
            using (var sr = new StringReader(text))
            using (var reader = new JsonTextReader(sr)
            {
                DateParseHandling = DateParseHandling.None,
                FloatParseHandling = FloatParseHandling.Double,
            })
            {
                var token = JToken.ReadFrom(reader, Load);
                if (reader.Read()) throw new JsonReaderException("additional content after the JSON value");
                return token;
            }
        }

        /// <summary>Replace number tokens that overflow a double with Infinity / -Infinity (and underflow with 0),
        /// as Python's float() does. Returns the same instance when nothing changed. Assumes valid syntax.</summary>
        internal static string NormaliseOverflow(string s)
        {
            System.Text.StringBuilder sb = null;
            int last = 0, i = 0;
            while (i < s.Length)
            {
                char c = s[i];
                if (c == '"')
                {
                    i++;
                    while (i < s.Length && s[i] != '"') i += s[i] == '\\' ? 2 : 1;
                    i++;
                    continue;
                }
                bool start = (c >= '0' && c <= '9') || (c == '-' && i + 1 < s.Length && s[i + 1] >= '0' && s[i + 1] <= '9');
                if (!start) { i++; continue; }
                int j = i + 1;
                while (j < s.Length && ((s[j] >= '0' && s[j] <= '9') || s[j] == '.' || s[j] == 'e' || s[j] == 'E' || s[j] == '+' || s[j] == '-')) j++;
                string tok = s.Substring(i, j - i);
                double d;
                if (!double.TryParse(tok, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out d))
                {
                    int e = tok.IndexOfAny(new[] { 'e', 'E' });
                    bool negExp = e >= 0 && e + 1 < tok.Length && tok[e + 1] == '-';
                    string rep = negExp ? "0.0" : (tok[0] == '-' ? "-Infinity" : "Infinity");
                    if (sb == null) sb = new System.Text.StringBuilder(s.Length + 8);
                    sb.Append(s, last, i - last).Append(rep);
                    last = j;
                }
                i = j;
            }
            if (sb == null) return s;
            sb.Append(s, last, s.Length - last);
            return sb.ToString();
        }

        /// <summary>Validate RFC 8259 syntax (plus NaN/Infinity/-Infinity literals). Throws JsonReaderException.</summary>
        public static void CheckSyntax(string s)
        {
            int i = 0;
            SkipWs(s, ref i);
            Value(s, ref i, 0);
            SkipWs(s, ref i);
            if (i != s.Length) Fail(i, "additional content after the JSON value");
        }

        private const int MaxDepth = 64;

        private static void Value(string s, ref int i, int depth)
        {
            if (depth > MaxDepth) Fail(i, "nesting too deep");
            if (i >= s.Length) Fail(i, "unexpected end of input");
            char c = s[i];
            switch (c)
            {
                case '{': Obj(s, ref i, depth); return;
                case '[': Arr(s, ref i, depth); return;
                case '"': Str(s, ref i); return;
                case 't': Lit(s, ref i, "true"); return;
                case 'f': Lit(s, ref i, "false"); return;
                case 'n': Lit(s, ref i, "null"); return;
                case 'N': Lit(s, ref i, "NaN"); return;
                case 'I': Lit(s, ref i, "Infinity"); return;
                default:
                    if (c == '-' || (c >= '0' && c <= '9')) { Num(s, ref i); return; }
                    Fail(i, "unexpected character '" + c + "'");
                    return;
            }
        }

        private static void Obj(string s, ref int i, int depth)
        {
            i++; // {
            SkipWs(s, ref i);
            if (i < s.Length && s[i] == '}') { i++; return; }
            while (true)
            {
                SkipWs(s, ref i);
                if (i >= s.Length || s[i] != '"') Fail(i, "object keys must be double-quoted strings");
                Str(s, ref i);
                SkipWs(s, ref i);
                if (i >= s.Length || s[i] != ':') Fail(i, "expected ':'");
                i++;
                SkipWs(s, ref i);
                Value(s, ref i, depth + 1);
                SkipWs(s, ref i);
                if (i >= s.Length) Fail(i, "unterminated object");
                if (s[i] == ',') { i++; SkipWs(s, ref i); if (i < s.Length && s[i] == '}') Fail(i, "trailing comma"); continue; }
                if (s[i] == '}') { i++; return; }
                Fail(i, "expected ',' or '}'");
            }
        }

        private static void Arr(string s, ref int i, int depth)
        {
            i++; // [
            SkipWs(s, ref i);
            if (i < s.Length && s[i] == ']') { i++; return; }
            while (true)
            {
                SkipWs(s, ref i);
                Value(s, ref i, depth + 1);
                SkipWs(s, ref i);
                if (i >= s.Length) Fail(i, "unterminated array");
                if (s[i] == ',') { i++; SkipWs(s, ref i); if (i < s.Length && s[i] == ']') Fail(i, "trailing comma"); continue; }
                if (s[i] == ']') { i++; return; }
                Fail(i, "expected ',' or ']'");
            }
        }

        private static void Str(string s, ref int i)
        {
            i++; // opening quote
            while (i < s.Length)
            {
                char c = s[i];
                if (c == '"') { i++; return; }
                if (c < 0x20) Fail(i, "control character in string");
                if (c == '\\')
                {
                    i++;
                    if (i >= s.Length) break;
                    char e = s[i];
                    if (e == 'u')
                    {
                        if (i + 4 >= s.Length) Fail(i, "bad \\u escape");
                        for (int k = 1; k <= 4; k++)
                            if (!IsHex(s[i + k])) Fail(i + k, "bad \\u escape");
                        i += 5;
                        continue;
                    }
                    if (e != '"' && e != '\\' && e != '/' && e != 'b' && e != 'f' && e != 'n' && e != 'r' && e != 't')
                        Fail(i, "invalid escape '\\" + e + "'");
                    i++;
                    continue;
                }
                i++;
            }
            Fail(i, "unterminated string");
        }

        private static void Num(string s, ref int i)
        {
            if (s[i] == '-')
            {
                i++;
                if (i < s.Length && s[i] == 'I') { Lit(s, ref i, "Infinity"); return; }
            }
            if (i >= s.Length) Fail(i, "incomplete number");
            if (s[i] == '0') i++;
            else if (s[i] >= '1' && s[i] <= '9') { while (i < s.Length && s[i] >= '0' && s[i] <= '9') i++; }
            else Fail(i, "invalid number");
            if (i < s.Length && s[i] == '.')
            {
                i++;
                if (i >= s.Length || s[i] < '0' || s[i] > '9') Fail(i, "digit expected after '.'");
                while (i < s.Length && s[i] >= '0' && s[i] <= '9') i++;
            }
            if (i < s.Length && (s[i] == 'e' || s[i] == 'E'))
            {
                i++;
                if (i < s.Length && (s[i] == '+' || s[i] == '-')) i++;
                if (i >= s.Length || s[i] < '0' || s[i] > '9') Fail(i, "digit expected in exponent");
                while (i < s.Length && s[i] >= '0' && s[i] <= '9') i++;
            }
            if (i < s.Length && ((s[i] >= '0' && s[i] <= '9') || char.IsLetter(s[i]) || s[i] == '.'))
                Fail(i, "invalid number");
        }

        private static void Lit(string s, ref int i, string lit)
        {
            if (string.CompareOrdinal(s, i, lit, 0, lit.Length) != 0) Fail(i, "invalid literal");
            i += lit.Length;
        }

        private static void SkipWs(string s, ref int i)
        {
            while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) i++;
        }

        private static bool IsHex(char c) => (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');

        private static void Fail(int pos, string message) => throw new JsonReaderException(message + " at position " + pos);
    }
}
