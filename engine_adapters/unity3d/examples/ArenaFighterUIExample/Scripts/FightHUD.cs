using ArenaFighterExample;
using UnityEngine;
using UnityEngine.UI;

namespace ArenaFighterUIExample
{
    /// <summary>
    /// Simple screen-space overlay showing fight status, HP values, and combat log.
    /// Attached to a canvas that covers the whole screen.
    /// </summary>
    [DisallowMultipleComponent]
    public class FightHUD : MonoBehaviour
    {
        private ArenaFighterGameMode _gameMode;
        private Text _statusText;
        private Text _logText;
        private Canvas _canvas;
        private string _logBuffer = "";
        private float _lastPlayerHP;
        private float _lastOpponentHP;

        void Start()
        {
            _gameMode = FindObjectOfType<ArenaFighterGameMode>();
            if (_gameMode == null) return;

            CreateHUD();
            _lastPlayerHP = _gameMode.Player != null ? _gameMode.Player.Health : 0f;
            _lastOpponentHP = _gameMode.Opponent != null ? _gameMode.Opponent.Health : 0f;
            UpdateHUD();
        }

        void CreateHUD()
        {
            var canvasObj = new GameObject("FightHUD");
            canvasObj.transform.SetParent(transform, false);

            _canvas = canvasObj.AddComponent<Canvas>();
            _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvasObj.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            canvasObj.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1920, 1080);
            canvasObj.AddComponent<GraphicRaycaster>();

            // Status text (top center) — shows "FIGHT!" / "Player Wins!" / "Opponent Wins!"
            var statusObj = new GameObject("StatusText");
            statusObj.transform.SetParent(canvasObj.transform, false);
            _statusText = statusObj.AddComponent<Text>();
            _statusText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            _statusText.fontSize = 36;
            _statusText.alignment = TextAnchor.UpperCenter;
            _statusText.color = Color.white;
            var statusRect = statusObj.GetComponent<RectTransform>();
            statusRect.anchorMin = new Vector2(0.3f, 0.85f);
            statusRect.anchorMax = new Vector2(0.7f, 1f);
            statusRect.offsetMin = Vector2.zero;
            statusRect.offsetMax = Vector2.zero;

            // Combat log (bottom left)
            var logObj = new GameObject("LogText");
            logObj.transform.SetParent(canvasObj.transform, false);
            _logText = logObj.AddComponent<Text>();
            _logText.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            _logText.fontSize = 18;
            _logText.alignment = TextAnchor.LowerLeft;
            _logText.color = new Color(1f, 1f, 1f, 0.85f);
            _logText.supportRichText = true;
            var logRect = logObj.GetComponent<RectTransform>();
            logRect.anchorMin = new Vector2(0f, 0f);
            logRect.anchorMax = new Vector2(0.45f, 0.3f);
            logRect.offsetMin = new Vector2(20f, 20f);
            logRect.offsetMax = new Vector2(0f, 0f);
        }

        void Update()
        {
            if (_gameMode == null) return;

            // Detect HP changes and log them
            if (_gameMode.Player != null && _gameMode.Opponent != null)
            {
                float pHP = _gameMode.Player.Health;
                float oHP = _gameMode.Opponent.Health;

                if (!Mathf.Approximately(pHP, _lastPlayerHP))
                {
                    float diff = _lastPlayerHP - pHP;
                    if (diff > 0f)
                        AppendLog($"<color=#ff6666>Opponent hit Player for {diff:F0} damage! (HP: {pHP:F0})</color>");
                    _lastPlayerHP = pHP;
                }

                if (!Mathf.Approximately(oHP, _lastOpponentHP))
                {
                    float diff = _lastOpponentHP - oHP;
                    if (diff > 0f)
                        AppendLog($"<color=#66aaff>Player hit Opponent for {diff:F0} damage! (HP: {oHP:F0})</color>");
                    _lastOpponentHP = oHP;
                }

                if (_gameMode.Player.IsDead)
                    AppendLog("<color=#ff4444>Player has been defeated!</color>");
                if (_gameMode.Opponent.IsDead)
                    AppendLog("<color=#44ff44>Opponent has been defeated!</color>");
            }

            UpdateHUD();
        }

        void UpdateHUD()
        {
            if (_statusText == null) return;

            if (_gameMode == null) return;

            string status;
            if (!_gameMode.IsRoundActive)
            {
                status = _gameMode.PlayerWon ? "PLAYER WINS!" : "OPPONENT WINS!";
            }
            else
            {
                float pHP = _gameMode.Player != null ? _gameMode.Player.Health : 0f;
                float oHP = _gameMode.Opponent != null ? _gameMode.Opponent.Health : 0f;
                status = $"Player: {pHP:F0}  vs  Opponent: {oHP:F0}";
            }

            _statusText.text = status;

            if (_logText != null)
                _logText.text = _logBuffer;
        }

        void AppendLog(string entry)
        {
            string timestamp = $"[{Time.time:F1}s] ";
            _logBuffer = timestamp + entry + "\n" + _logBuffer;

            // Keep only last 8 lines
            var lines = _logBuffer.Split('\n');
            if (lines.Length > 9)
                _logBuffer = string.Join("\n", lines, 0, 9);
        }
    }
}
