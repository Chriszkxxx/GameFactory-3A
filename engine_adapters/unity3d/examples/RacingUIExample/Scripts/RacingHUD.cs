using RacingExample;
using UnityEngine;
using UnityEngine.UI;

namespace RacingUIExample
{
    [DisallowMultipleComponent]
    public sealed class RacingHUD : MonoBehaviour
    {
        [SerializeField] private RacingGameMode gameMode;

        private Text speedText;
        private Text lapText;
        private Text checkpointText;
        private Text resultText;
        private GameObject resultOverlay;
        private Button restartButton;
        private bool subscribed;
        private GameObject interfaceRoot;

        public string SpeedLabel => speedText != null ? speedText.text : string.Empty;
        public string LapLabel => lapText != null ? lapText.text : string.Empty;
        public string CheckpointLabel =>
            checkpointText != null ? checkpointText.text : string.Empty;
        public string ResultLabel => resultText != null ? resultText.text : string.Empty;
        public bool ResultVisible => resultOverlay != null && resultOverlay.activeSelf;
        public Button RestartButton => restartButton;

        void Awake()
        {
            EnsureInterface();
        }

        void Start()
        {
            Bind(gameMode != null ? gameMode : FindObjectOfType<RacingGameMode>());
        }

        void OnDestroy()
        {
            Unsubscribe();
        }

        void Update()
        {
            Refresh();
            if (ResultVisible &&
                (Input.GetKeyDown(KeyCode.Return) ||
                 Input.GetKeyDown(KeyCode.KeypadEnter)))
                Restart();
        }

        public void Bind(RacingGameMode mode)
        {
            EnsureInterface();
            Unsubscribe();
            gameMode = mode;
            if (gameMode == null)
                return;

            gameMode.OnRaceStarted += HandleRaceStarted;
            gameMode.OnCheckpointPassed += Refresh;
            gameMode.OnLapCompleted += Refresh;
            gameMode.OnRaceFinished += HandleRaceFinished;
            gameMode.OnStateChanged += Refresh;
            subscribed = true;
            Refresh();
        }

        public void Refresh()
        {
            EnsureInterface();
            if (gameMode == null)
                return;

            speedText.text = string.Format("Speed: {0:0}", gameMode.VehicleSpeed);
            lapText.text = string.Format(
                "Lap {0} / {1}",
                Mathf.Min(gameMode.CurrentLap, gameMode.TotalLaps),
                gameMode.TotalLaps);
            checkpointText.text = string.Format(
                "Checkpoint {0} / {1}",
                gameMode.CheckpointsPassed,
                gameMode.TotalCheckpoints);
        }

        public void Restart()
        {
            if (gameMode != null)
                gameMode.Restart();
            if (resultOverlay != null)
                resultOverlay.SetActive(false);
            Refresh();
        }

        private void HandleRaceStarted()
        {
            EnsureInterface();
            resultOverlay.SetActive(false);
            Refresh();
        }

        private void HandleRaceFinished()
        {
            EnsureInterface();
            resultText.text = "RACE FINISHED";
            resultOverlay.SetActive(true);
            Refresh();
        }

        private void Unsubscribe()
        {
            if (!subscribed || gameMode == null)
                return;

            gameMode.OnRaceStarted -= HandleRaceStarted;
            gameMode.OnCheckpointPassed -= Refresh;
            gameMode.OnLapCompleted -= Refresh;
            gameMode.OnRaceFinished -= HandleRaceFinished;
            gameMode.OnStateChanged -= Refresh;
            subscribed = false;
        }

        private void EnsureInterface()
        {
            if (interfaceRoot != null && speedText != null && lapText != null &&
                checkpointText != null && resultText != null &&
                resultOverlay != null && restartButton != null)
                return;

            BuildInterface();
        }

        private void BuildInterface()
        {
            GameObject root = new GameObject("RacingHUDCanvas");
            interfaceRoot = root;
            root.transform.SetParent(transform, false);
            Canvas canvas = root.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 50;
            CanvasScaler scaler = root.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            root.AddComponent<GraphicRaycaster>();

            Font font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            speedText = CreateText(root.transform, "SpeedLabel", font, 40,
                TextAnchor.MiddleLeft, new Vector2(0.03f, 0.04f),
                new Vector2(0.28f, 0.13f));
            lapText = CreateText(root.transform, "LapLabel", font, 32,
                TextAnchor.MiddleCenter, new Vector2(0.38f, 0.9f),
                new Vector2(0.62f, 0.98f));
            checkpointText = CreateText(root.transform, "CheckpointLabel", font, 24,
                TextAnchor.MiddleCenter, new Vector2(0.38f, 0.84f),
                new Vector2(0.62f, 0.9f));

            resultOverlay = new GameObject(
                "RaceResultOverlay", typeof(RectTransform), typeof(Image));
            resultOverlay.transform.SetParent(root.transform, false);
            RectTransform overlayRect = resultOverlay.GetComponent<RectTransform>();
            overlayRect.anchorMin = Vector2.zero;
            overlayRect.anchorMax = Vector2.one;
            overlayRect.offsetMin = overlayRect.offsetMax = Vector2.zero;
            resultOverlay.GetComponent<Image>().color = new Color(0.02f, 0.03f, 0.04f, 0.88f);

            resultText = CreateText(resultOverlay.transform, "ResultLabel", font, 64,
                TextAnchor.MiddleCenter, new Vector2(0.2f, 0.52f),
                new Vector2(0.8f, 0.72f));
            resultText.text = "RACE FINISHED";
            resultText.color = new Color(0.2f, 0.9f, 0.55f);
            restartButton = CreateButton(resultOverlay.transform, font, Restart);
            resultOverlay.SetActive(false);
        }

        private static Text CreateText(
            Transform parent,
            string name,
            Font font,
            int fontSize,
            TextAnchor alignment,
            Vector2 anchorMin,
            Vector2 anchorMax)
        {
            GameObject item = new GameObject(name, typeof(RectTransform), typeof(Text));
            item.transform.SetParent(parent, false);
            RectTransform rect = item.GetComponent<RectTransform>();
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.offsetMin = rect.offsetMax = Vector2.zero;
            Text text = item.GetComponent<Text>();
            text.font = font;
            text.fontSize = fontSize;
            text.alignment = alignment;
            text.color = Color.white;
            return text;
        }

        private static Button CreateButton(
            Transform parent,
            Font font,
            UnityEngine.Events.UnityAction action)
        {
            GameObject item = new GameObject(
                "RestartButton", typeof(RectTransform), typeof(Image), typeof(Button));
            item.transform.SetParent(parent, false);
            RectTransform rect = item.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.4f, 0.35f);
            rect.anchorMax = new Vector2(0.6f, 0.43f);
            rect.offsetMin = rect.offsetMax = Vector2.zero;
            item.GetComponent<Image>().color = new Color(0.12f, 0.48f, 0.3f, 1f);
            Button button = item.GetComponent<Button>();
            button.onClick.AddListener(action);
            Text label = CreateText(item.transform, "Label", font, 22,
                TextAnchor.MiddleCenter, Vector2.zero, Vector2.one);
            label.text = "Restart Race";
            return button;
        }
    }
}
