using FPSExample;
using UnityEngine;
using UnityEngine.UI;

namespace FPSUIExample
{
    [DisallowMultipleComponent]
    public sealed class FPSArenaHUD : MonoBehaviour
    {
        private const float DamageFlashSeconds = 0.3f;
        private const float HitMarkerSeconds = 0.2f;

        [SerializeField] private FPSGameRuntimeAdapter adapter;

        private Canvas canvas;
        private Text healthText;
        private Text ammoText;
        private Text killText;
        private Text timerText;
        private Image healthFill;
        private Image damageFlash;
        private CanvasGroup hitMarker;
        private GameObject gameOverOverlay;
        private Text gameOverTitle;
        private Text gameOverStats;
        private Button restartButton;
        private float damageFlashRemaining;
        private float hitMarkerRemaining;
        private bool subscribed;

        public string HealthLabel => healthText != null ? healthText.text : string.Empty;
        public string AmmoLabel => ammoText != null ? ammoText.text : string.Empty;
        public string KillLabel => killText != null ? killText.text : string.Empty;
        public string TimerLabel => timerText != null ? timerText.text : string.Empty;
        public string GameOverTitle => gameOverTitle != null ? gameOverTitle.text : string.Empty;
        public bool GameOverVisible => gameOverOverlay != null && gameOverOverlay.activeSelf;
        public float DamageFlashAlpha => damageFlash != null ? damageFlash.color.a : 0f;
        public float HitMarkerAlpha => hitMarker != null ? hitMarker.alpha : 0f;
        public Button RestartButton => restartButton;

        private void Awake()
        {
            EnsureInterface();
        }

        private void Start()
        {
            Bind(adapter != null ? adapter : FindObjectOfType<FPSGameRuntimeAdapter>());
        }

        private void OnDestroy()
        {
            Unsubscribe();
        }

        public void Bind(FPSGameRuntimeAdapter runtimeAdapter)
        {
            EnsureInterface();
            Unsubscribe();
            adapter = runtimeAdapter;
            if (adapter == null) return;
            adapter.OnPlayerDamaged += HandlePlayerDamaged;
            adapter.OnEnemyKilled += HandleEnemyKilled;
            adapter.OnWeaponFired += Refresh;
            adapter.OnWeaponReload += Refresh;
            adapter.OnGameWin += HandleGameWin;
            adapter.OnGameLose += HandleGameLose;
            subscribed = true;
            Refresh();
        }

        private void Unsubscribe()
        {
            if (!subscribed || adapter == null) return;
            adapter.OnPlayerDamaged -= HandlePlayerDamaged;
            adapter.OnEnemyKilled -= HandleEnemyKilled;
            adapter.OnWeaponFired -= Refresh;
            adapter.OnWeaponReload -= Refresh;
            adapter.OnGameWin -= HandleGameWin;
            adapter.OnGameLose -= HandleGameLose;
            subscribed = false;
        }

        private void Update()
        {
            Refresh();
            AdvanceEffects(Time.deltaTime);
            if (GameOverVisible &&
                (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter)))
                Restart();
        }

        public void Refresh()
        {
            EnsureInterface();
            if (adapter == null || healthText == null) return;
            healthText.text = string.Format(
                "HP: {0:0}/{1:0}",
                adapter.PlayerHealth,
                adapter.PlayerMaxHealth);
            float healthRatio = adapter.PlayerMaxHealth > 0f
                ? Mathf.Clamp01(adapter.PlayerHealth / adapter.PlayerMaxHealth)
                : 0f;
            healthFill.fillAmount = healthRatio;
            healthFill.color = HealthColor(healthRatio);
            ammoText.text = adapter.IsReloading
                ? "RELOADING..."
                : string.Format("{0} / {1}", adapter.PlayerAmmo, adapter.MagazineSize);
            killText.text = "Kills: " + adapter.EnemiesKilled + " / 3";
            timerText.text = FormatTimer(adapter.TimeRemaining);
        }

        public void AdvanceEffects(float deltaTime)
        {
            damageFlashRemaining = Mathf.Max(0f, damageFlashRemaining - deltaTime);
            hitMarkerRemaining = Mathf.Max(0f, hitMarkerRemaining - deltaTime);
            Color flash = damageFlash.color;
            flash.a = 0.45f * Mathf.Clamp01(damageFlashRemaining / DamageFlashSeconds);
            damageFlash.color = flash;
            hitMarker.alpha = Mathf.Clamp01(hitMarkerRemaining / HitMarkerSeconds);
        }

        private void HandlePlayerDamaged(float amount)
        {
            damageFlashRemaining = DamageFlashSeconds;
            AdvanceEffects(0f);
            Refresh();
        }

        private void HandleEnemyKilled()
        {
            hitMarkerRemaining = HitMarkerSeconds;
            AdvanceEffects(0f);
            Refresh();
        }

        private void HandleGameWin()
        {
            ShowGameOver(FPSGameStatus.Won);
        }

        private void HandleGameLose()
        {
            ShowGameOver(FPSGameStatus.Lost);
        }

        public void ShowGameOver(FPSGameStatus status)
        {
            EnsureInterface();
            gameOverOverlay.SetActive(true);
            bool won = status == FPSGameStatus.Won;
            gameOverTitle.text = won ? "ARENA CLEARED!" : "YOU DIED";
            gameOverTitle.color = won
                ? new Color(0.22f, 0.9f, 0.42f)
                : new Color(1f, 0.24f, 0.22f);
            int kills = adapter != null ? adapter.EnemiesKilled : 0;
            float elapsed = adapter != null ? 60f - adapter.TimeRemaining : 0f;
            gameOverStats.text = string.Format("Kills: {0}\nTime: {1:0.0}s", kills, elapsed);
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }

        public void Restart()
        {
            if (adapter != null) adapter.ResetGame();
            gameOverOverlay.SetActive(false);
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
            Refresh();
        }

        public static string FormatTimer(float seconds)
        {
            int total = Mathf.Clamp(Mathf.CeilToInt(seconds), 0, 60);
            return string.Format("00:{0:00}", total);
        }

        public static Color HealthColor(float ratio)
        {
            ratio = Mathf.Clamp01(ratio);
            return ratio >= 0.5f
                ? Color.Lerp(new Color(1f, 0.72f, 0.1f), new Color(0.2f, 0.9f, 0.35f), (ratio - 0.5f) * 2f)
                : Color.Lerp(new Color(0.95f, 0.15f, 0.12f), new Color(1f, 0.72f, 0.1f), ratio * 2f);
        }

        private void EnsureInterface()
        {
            if (canvas != null)
                return;
            BuildInterface();
        }

        private void BuildInterface()
        {
            GameObject root = new GameObject("FPSArenaHUDCanvas");
            root.transform.SetParent(transform, false);
            canvas = root.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 50;
            CanvasScaler scaler = root.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            root.AddComponent<GraphicRaycaster>();

            damageFlash = CreateImage(root.transform, "DamageFlash", Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero, new Color(0.7f, 0f, 0f, 0f));
            BuildCrosshair(root.transform);
            BuildHealth(root.transform);
            Font font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            healthText = CreateText(root.transform, "HealthLabel", font, 25, TextAnchor.MiddleLeft, new Vector2(0.025f, 0.035f), new Vector2(0.25f, 0.095f));
            ammoText = CreateText(root.transform, "AmmoLabel", font, 32, TextAnchor.MiddleRight, new Vector2(0.75f, 0.035f), new Vector2(0.975f, 0.105f));
            killText = CreateText(root.transform, "KillLabel", font, 28, TextAnchor.MiddleCenter, new Vector2(0.4f, 0.91f), new Vector2(0.6f, 0.975f));
            timerText = CreateText(root.transform, "TimerLabel", font, 28, TextAnchor.MiddleRight, new Vector2(0.82f, 0.91f), new Vector2(0.975f, 0.975f));
            BuildGameOver(root.transform, font);
        }

        private void BuildHealth(Transform parent)
        {
            CreateImage(parent, "HealthBackground", new Vector2(0.025f, 0.02f), new Vector2(0.25f, 0.035f), Vector2.zero, Vector2.zero, new Color(0.05f, 0.06f, 0.07f, 0.9f));
            healthFill = CreateImage(parent, "HealthFill", new Vector2(0.025f, 0.02f), new Vector2(0.25f, 0.035f), Vector2.zero, Vector2.zero, new Color(0.2f, 0.9f, 0.35f));
            healthFill.type = Image.Type.Filled;
            healthFill.fillMethod = Image.FillMethod.Horizontal;
        }

        private void BuildCrosshair(Transform parent)
        {
            Color color = new Color(0.95f, 0.98f, 1f, 0.95f);
            CreateImage(parent, "CrosshairDot", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-2f, -2f), new Vector2(2f, 2f), color);
            CreateImage(parent, "CrosshairTop", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-1f, 9f), new Vector2(1f, 22f), color);
            CreateImage(parent, "CrosshairBottom", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-1f, -22f), new Vector2(1f, -9f), color);
            CreateImage(parent, "CrosshairLeft", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-22f, -1f), new Vector2(-9f, 1f), color);
            CreateImage(parent, "CrosshairRight", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(9f, -1f), new Vector2(22f, 1f), color);
            GameObject marker = new GameObject("HitMarker", typeof(RectTransform), typeof(CanvasGroup));
            marker.transform.SetParent(parent, false);
            RectTransform rect = marker.GetComponent<RectTransform>();
            rect.anchorMin = rect.anchorMax = new Vector2(0.5f, 0.5f);
            rect.sizeDelta = new Vector2(42f, 42f);
            hitMarker = marker.GetComponent<CanvasGroup>();
            hitMarker.alpha = 0f;
            Image slashA = CreateImage(marker.transform, "SlashA", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-1.5f, -17f), new Vector2(1.5f, 17f), Color.white);
            slashA.rectTransform.localRotation = Quaternion.Euler(0f, 0f, 45f);
            Image slashB = CreateImage(marker.transform, "SlashB", new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-1.5f, -17f), new Vector2(1.5f, 17f), Color.white);
            slashB.rectTransform.localRotation = Quaternion.Euler(0f, 0f, -45f);
        }

        private void BuildGameOver(Transform parent, Font font)
        {
            gameOverOverlay = new GameObject("GameOverOverlay", typeof(RectTransform), typeof(Image));
            gameOverOverlay.transform.SetParent(parent, false);
            RectTransform overlayRect = gameOverOverlay.GetComponent<RectTransform>();
            overlayRect.anchorMin = Vector2.zero;
            overlayRect.anchorMax = Vector2.one;
            overlayRect.offsetMin = overlayRect.offsetMax = Vector2.zero;
            gameOverOverlay.GetComponent<Image>().color = new Color(0.02f, 0.025f, 0.03f, 0.88f);
            gameOverTitle = CreateText(gameOverOverlay.transform, "GameOverTitle", font, 72, TextAnchor.MiddleCenter, new Vector2(0.2f, 0.58f), new Vector2(0.8f, 0.75f));
            gameOverStats = CreateText(gameOverOverlay.transform, "GameOverStats", font, 30, TextAnchor.MiddleCenter, new Vector2(0.3f, 0.4f), new Vector2(0.7f, 0.56f));
            restartButton = CreateButton(gameOverOverlay.transform, font, Restart);
            gameOverOverlay.SetActive(false);
        }

        private static Text CreateText(Transform parent, string name, Font font, int size, TextAnchor alignment, Vector2 min, Vector2 max)
        {
            GameObject item = new GameObject(name, typeof(RectTransform), typeof(Text));
            item.transform.SetParent(parent, false);
            Text text = item.GetComponent<Text>();
            text.font = font;
            text.fontSize = size;
            text.alignment = alignment;
            text.color = Color.white;
            text.raycastTarget = false;
            RectTransform rect = text.rectTransform;
            rect.anchorMin = min;
            rect.anchorMax = max;
            rect.offsetMin = rect.offsetMax = Vector2.zero;
            return text;
        }

        private static Image CreateImage(Transform parent, string name, Vector2 min, Vector2 max, Vector2 offsetMin, Vector2 offsetMax, Color color)
        {
            GameObject item = new GameObject(name, typeof(RectTransform), typeof(Image));
            item.transform.SetParent(parent, false);
            Image image = item.GetComponent<Image>();
            image.color = color;
            image.raycastTarget = false;
            RectTransform rect = image.rectTransform;
            rect.anchorMin = min;
            rect.anchorMax = max;
            rect.offsetMin = offsetMin;
            rect.offsetMax = offsetMax;
            return image;
        }

        private static Button CreateButton(Transform parent, Font font, UnityEngine.Events.UnityAction action)
        {
            GameObject item = new GameObject("RestartButton", typeof(RectTransform), typeof(Image), typeof(Button));
            item.transform.SetParent(parent, false);
            RectTransform rect = item.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0.41f, 0.27f);
            rect.anchorMax = new Vector2(0.59f, 0.34f);
            rect.offsetMin = rect.offsetMax = Vector2.zero;
            item.GetComponent<Image>().color = new Color(0.16f, 0.2f, 0.24f, 1f);
            Button button = item.GetComponent<Button>();
            button.onClick.AddListener(action);
            Text label = CreateText(item.transform, "Label", font, 22, TextAnchor.MiddleCenter, Vector2.zero, Vector2.one);
            label.text = "Press Enter to Restart";
            return button;
        }
    }
}
