using MCPForUnity.Editor.Services;
using UnityEditor;
using UnityEngine;

namespace QIWEN.Editor
{
    [InitializeOnLoad]
    public static class QIWENMcpBootstrap
    {
        private const string SessionKey = "QIWEN.McpBootstrap.Connected";

        static QIWENMcpBootstrap()
        {
            EditorPrefs.SetBool("MCPForUnity.UseHttpTransport", true);
            EditorPrefs.SetString("MCPForUnity.HttpTransportScope", "local");
            EditorPrefs.SetString("MCPForUnity.HttpUrl", "http://127.0.0.1:8080");
            EditorPrefs.SetString("MCPForUnity.UvxPath", "D:\\qiwen-runtime\\tools\\uv\\uvx.exe");
            EditorPrefs.SetBool("MCPForUnity.AutoStartOnLoad", true);
            EditorApplication.delayCall += Connect;
        }

        private static async void Connect()
        {
            if (SessionState.GetBool(SessionKey, false) && MCPServiceLocator.Bridge.IsRunning)
            {
                return;
            }

            bool connected = await MCPServiceLocator.Bridge.StartAsync();
            SessionState.SetBool(SessionKey, connected);
            Debug.Log(connected
                ? "[漆问] Unity MCP 已连接到 http://127.0.0.1:8080"
                : "[漆问] Unity MCP 连接失败，将由自动重连继续尝试");
        }
    }
}
