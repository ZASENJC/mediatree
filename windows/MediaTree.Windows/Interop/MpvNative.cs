using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Interop;

internal static class MpvNative
{
    private const string MpvLibrary = "mpv-2";
    private const string D3D11CompositionOption = "d3d11-output-mode=composition";
    public static string MpvDllPath => Path.Combine(AppPaths.MpvDirectory, "mpv-2.dll");

    static MpvNative()
    {
        NativeLibrary.SetDllImportResolver(typeof(MpvNative).Assembly, ResolveNativeLibrary);
    }

    public static IntPtr Create()
    {
        if (!File.Exists(MpvDllPath))
        {
            throw new FileNotFoundException("Bundled mpv-2.dll was not found. Rebuild the Windows package with bundled mpv.", MpvDllPath);
        }

        var path = Environment.GetEnvironmentVariable("PATH") ?? "";
        if (!path.Contains(AppPaths.MpvDirectory, StringComparison.OrdinalIgnoreCase))
        {
            Environment.SetEnvironmentVariable("PATH", AppPaths.MpvDirectory + ";" + path);
        }

        return mpv_create();
    }

    public static void InitializeForD3D11Composition(IntPtr handle)
    {
        SetOption(handle, "terminal", "no");
        SetOption(handle, "idle", "yes");
        SetOption(handle, "force-window", "no");
        TrySetOption(handle, "osc", "yes");
        TrySetOption(handle, "input-default-bindings", "yes");
        TrySetOption(handle, "osd-level", "1");
        TrySetOption(handle, "osd-duration", "1200");
        TrySetOption(handle, "cursor-autohide", "1000");
        TrySetOption(handle, "script-opts", "osc-layout=bottombar,osc-seekbarstyle=bar,osc-visibility=auto");
        SetOption(handle, "vo", "gpu-next");
        SetOption(handle, "gpu-api", "d3d11");
        SetOption(handle, "gpu-context", "d3d11");
        SetOption(handle, "d3d11-output-mode", "composition");
        SetOption(handle, "hwdec", "auto-safe");
        Check(mpv_initialize(handle), "mpv_initialize");
        _ = mpv_observe_property(handle, 1, "time-pos", MpvFormat.Double);
        _ = mpv_observe_property(handle, 2, "duration", MpvFormat.Double);
        _ = mpv_observe_property(handle, 3, "pause", MpvFormat.Flag);
    }

    public static void SetD3D11CompositionSize(IntPtr handle, double width, double height)
    {
        if (handle == IntPtr.Zero || width <= 0 || height <= 0)
        {
            return;
        }

        SetOption(handle, "d3d11-composition-size", $"{Math.Round(width)}x{Math.Round(height)}");
    }

    public static void Command(IntPtr handle, params string[] args)
    {
        var ptrs = new IntPtr[args.Length + 1];
        try
        {
            for (var i = 0; i < args.Length; i++)
            {
                ptrs[i] = StringToUtf8(args[i]);
            }

            Check(mpv_command(handle, ptrs), "mpv_command");
        }
        finally
        {
            foreach (var ptr in ptrs)
            {
                if (ptr != IntPtr.Zero)
                {
                    Marshal.FreeHGlobal(ptr);
                }
            }
        }
    }

    public static double GetDouble(IntPtr handle, string name)
    {
        return mpv_get_property_double(handle, name, MpvFormat.Double, out var value) >= 0 ? value : 0;
    }

    public static long GetInt64(IntPtr handle, string name)
    {
        return mpv_get_property_int64(handle, name, MpvFormat.Int64, out var value) >= 0 ? value : 0;
    }

    public static bool GetFlag(IntPtr handle, string name)
    {
        return mpv_get_property_flag(handle, name, MpvFormat.Flag, out var value) >= 0 && value != 0;
    }

    public static string GetString(IntPtr handle, string name)
    {
        var result = mpv_get_property_string(handle, name, MpvFormat.String, out var value);
        if (result < 0 || value == IntPtr.Zero)
        {
            return "";
        }

        try
        {
            return Marshal.PtrToStringUTF8(value) ?? "";
        }
        finally
        {
            mpv_free(value);
        }
    }

    public static IntPtr GetDisplaySwapchain(IntPtr handle)
    {
        var result = mpv_get_property_int64(handle, "display-swapchain", MpvFormat.Int64, out var value);
        return result >= 0 && value != 0 ? new IntPtr(value) : IntPtr.Zero;
    }

    public static MpvEvent ReadEvent(IntPtr handle, double timeoutSeconds)
    {
        var ptr = mpv_wait_event(handle, timeoutSeconds);
        return ptr == IntPtr.Zero ? default : Marshal.PtrToStructure<MpvEvent>(ptr);
    }

    public static void Terminate(IntPtr handle)
    {
        if (handle != IntPtr.Zero)
        {
            mpv_terminate_destroy(handle);
        }
    }

    public static void SetOption(IntPtr handle, string name, string value)
    {
        Check(mpv_set_option_string(handle, name, value), $"mpv_set_option_string {name}");
    }

    private static void TrySetOption(IntPtr handle, string name, string value)
    {
        var result = mpv_set_option_string(handle, name, value);
        if (result < 0)
        {
            ShellLogger.Error($"Optional mpv option {name} failed with mpv error {result}.");
        }
    }

    private static void Check(int code, string operation)
    {
        if (code < 0)
        {
            throw new InvalidOperationException($"{operation} failed with mpv error {code}.");
        }
    }

    private static IntPtr StringToUtf8(string value)
    {
        var bytes = Encoding.UTF8.GetBytes(value);
        var ptr = Marshal.AllocHGlobal(bytes.Length + 1);
        Marshal.Copy(bytes, 0, ptr, bytes.Length);
        Marshal.WriteByte(ptr, bytes.Length, 0);
        return ptr;
    }

    private static IntPtr ResolveNativeLibrary(string libraryName, System.Reflection.Assembly assembly, DllImportSearchPath? searchPath)
    {
        if (libraryName == MpvLibrary && File.Exists(MpvDllPath))
        {
            return NativeLibrary.Load(MpvDllPath);
        }

        return IntPtr.Zero;
    }

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr mpv_create();

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_initialize(IntPtr handle);

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_set_option_string(IntPtr handle, [MarshalAs(UnmanagedType.LPUTF8Str)] string name, [MarshalAs(UnmanagedType.LPUTF8Str)] string data);

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_command(IntPtr handle, IntPtr[] args);

    [DllImport(MpvLibrary, EntryPoint = "mpv_get_property", CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_get_property_double(IntPtr handle, [MarshalAs(UnmanagedType.LPUTF8Str)] string name, MpvFormat format, out double data);

    [DllImport(MpvLibrary, EntryPoint = "mpv_get_property", CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_get_property_flag(IntPtr handle, [MarshalAs(UnmanagedType.LPUTF8Str)] string name, MpvFormat format, out int data);

    [DllImport(MpvLibrary, EntryPoint = "mpv_get_property", CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_get_property_int64(IntPtr handle, [MarshalAs(UnmanagedType.LPUTF8Str)] string name, MpvFormat format, out long data);

    [DllImport(MpvLibrary, EntryPoint = "mpv_get_property", CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_get_property_string(IntPtr handle, [MarshalAs(UnmanagedType.LPUTF8Str)] string name, MpvFormat format, out IntPtr data);

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern int mpv_observe_property(IntPtr handle, ulong replyUserData, [MarshalAs(UnmanagedType.LPUTF8Str)] string name, MpvFormat format);

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr mpv_wait_event(IntPtr handle, double timeout);

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern void mpv_free(IntPtr data);

    [DllImport(MpvLibrary, CallingConvention = CallingConvention.Cdecl)]
    private static extern void mpv_terminate_destroy(IntPtr handle);
}

internal enum MpvFormat
{
    None = 0,
    String = 1,
    OsdString = 2,
    Flag = 3,
    Int64 = 4,
    Double = 5,
}

[StructLayout(LayoutKind.Sequential)]
internal struct MpvEvent
{
    public int EventId;
    public int Error;
    public ulong ReplyUserData;
    public IntPtr Data;
}
