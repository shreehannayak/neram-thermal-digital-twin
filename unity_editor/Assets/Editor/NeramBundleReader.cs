using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Neram.EditorTools
{
    /// <summary>
    /// Reader for the binary scene bundle written by tools/gen_neram_scene.py (format in tools/meshgen/scene.py).
    /// Deliberately free of UnityEngine types so it can be compiled and run outside Unity
    /// (tools/dotnet/BundleCheck) against the exact bundle that ships in the project.
    /// </summary>
    public static class NeramBundleReader
    {
        public sealed class NodeData
        {
            public string Name, Parent, Region, Flags;
            public float[] Position = new float[3];
            public float[] Rotation = new float[4]; // x, y, z, w
        }

        public sealed class MeshData
        {
            public string Name, Parent, Material;
            public float[] Pivot = new float[3];
            public float[] Positions; // 3 per vertex, relative to the pivot (world axes)
            public float[] Normals;   // 3 per vertex
            public float[] Uvs;       // 2 per vertex
            public int[] Indices;     // 3 per triangle
            public int VertexCount => Positions.Length / 3;
        }

        public sealed class Bundle
        {
            public int Version;
            public readonly List<NodeData> Nodes = new List<NodeData>();
            public readonly List<MeshData> Meshes = new List<MeshData>();
        }

        private static string Str(BinaryReader br)
        {
            int n = br.ReadInt32();
            if (n < 0 || n > 4096) throw new InvalidDataException("bad string length " + n);
            return Encoding.UTF8.GetString(br.ReadBytes(n));
        }

        private static float[] Floats(BinaryReader br, int n)
        {
            var a = new float[n];
            for (int i = 0; i < n; i++) a[i] = br.ReadSingle();
            return a;
        }

        /// <summary>Parses and validates the bundle (magic, version, index ranges, finite values, node parents).</summary>
        public static Bundle Read(byte[] data)
        {
            if (data == null || data.Length < 12) throw new InvalidDataException("bundle is empty or truncated");
            var b = new Bundle();
            using (var br = new BinaryReader(new MemoryStream(data)))
            {
                var magic = Encoding.ASCII.GetString(br.ReadBytes(4));
                if (magic != "NRMB") throw new InvalidDataException("not a NERAM mesh bundle (magic '" + magic + "')");
                b.Version = br.ReadInt32();
                if (b.Version != 1) throw new InvalidDataException("unsupported bundle version " + b.Version);
                int nn = br.ReadInt32();
                var names = new HashSet<string>(StringComparer.Ordinal);
                for (int i = 0; i < nn; i++)
                {
                    var n = new NodeData { Name = Str(br), Parent = Str(br) };
                    n.Position = Floats(br, 3);
                    n.Rotation = Floats(br, 4);
                    n.Region = Str(br);
                    n.Flags = Str(br);
                    if (!names.Add(n.Name)) throw new InvalidDataException("duplicate node " + n.Name);
                    if (n.Parent.Length > 0 && !names.Contains(n.Parent)) throw new InvalidDataException("node " + n.Name + ": parent " + n.Parent + " not defined before it");
                    b.Nodes.Add(n);
                }
                int nm = br.ReadInt32();
                for (int i = 0; i < nm; i++)
                {
                    var m = new MeshData { Name = Str(br), Parent = Str(br), Material = Str(br) };
                    m.Pivot = Floats(br, 3);
                    int nv = br.ReadInt32(), ni = br.ReadInt32();
                    if (nv <= 0 || ni <= 0 || ni % 3 != 0) throw new InvalidDataException(m.Name + ": bad counts v=" + nv + " i=" + ni);
                    m.Positions = Floats(br, nv * 3);
                    m.Normals = Floats(br, nv * 3);
                    m.Uvs = Floats(br, nv * 2);
                    m.Indices = new int[ni];
                    for (int k = 0; k < ni; k++)
                    {
                        uint u = br.ReadUInt32();
                        if (u >= nv) throw new InvalidDataException(m.Name + ": index " + u + " out of range");
                        m.Indices[k] = (int)u;
                    }
                    foreach (var f in m.Positions) if (float.IsNaN(f) || float.IsInfinity(f)) throw new InvalidDataException(m.Name + ": non-finite vertex");
                    if (!names.Contains(m.Parent)) throw new InvalidDataException(m.Name + ": parent node " + m.Parent + " missing");
                    b.Meshes.Add(m);
                }
                if (br.BaseStream.Position != br.BaseStream.Length) throw new InvalidDataException("trailing bytes in bundle");
            }
            return b;
        }
    }
}
