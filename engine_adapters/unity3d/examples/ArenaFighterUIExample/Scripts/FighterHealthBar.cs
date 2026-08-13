using ArenaFighterExample;
using UnityEngine;
using UnityEngine.UI;

namespace ArenaFighterUIExample
{
    /// <summary>
    /// World-space health bar that floats above a fighter.
    /// Attaches automatically when the fighter spawns.
    /// </summary>
    [DisallowMultipleComponent]
    public class FighterHealthBar : MonoBehaviour
    {
        private ArenaFighterController _fighter;
        private Image _barFill;
        private Image _barBackground;
        private Text _label;
        private Canvas _canvas;
        private float _barWidth = 120f;
        private float _barHeight = 24f;

        void Start()
        {
            _fighter = GetComponent<ArenaFighterController>();
            if (_fighter == null) return;

            CreateHealthBar();
            UpdateBar();
        }

        void CreateHealthBar()
        {
            // World-space Canvas above the fighter
            var canvasObj = new GameObject("HealthBarCanvas");
            canvasObj.transform.SetParent(transform, false);
            canvasObj.transform.localPosition = new Vector3(0f, 2.2f, 0f);

            _canvas = canvasObj.AddComponent<Canvas>();
            _canvas.renderMode = RenderMode.WorldSpace;
            _canvas.worldCamera = Camera.main;

            var scaler = canvasObj.AddComponent<CanvasScaler>();
            scaler.dynamicPixelsPerUnit = 200f;

            canvasObj.AddComponent<GraphicRaycaster>();

            var rect = canvasObj.GetComponent<RectTransform>();
            rect.sizeDelta = new Vector2(_barWidth, _barHeight + 18f);

            // Background bar (dark)
            var bgObj = new GameObject("BarBackground");
            bgObj.transform.SetParent(canvasObj.transform, false);
            _barBackground = bgObj.AddComponent<Image>();
            _barBackground.color = new Color(0.15f, 0.15f, 0.15f, 0.85f);
            var bgRect = bgObj.GetComponent<RectTransform>();
            bgRect.anchorMin = new Vector2(0.5f, 0f);
            bgRect.anchorMax = new Vector2(0.5f, 0f);
            bgRect.pivot = new Vector2(0.5f, 0.5f);
            bgRect.sizeDelta = new Vector2(_barWidth, _barHeight);
            bgRect.anchoredPosition = new Vector2(0f, 0f);

            // Fill bar (green → yellow → red based on HP)
            var fillObj = new GameObject("BarFill");
            fillObj.transform.SetParent(bgObj.transform, false);
            _barFill = fillObj.AddComponent<Image>();
            _barFill.color = Color.green;
            _barFill.raycastTarget = false;
            var fillRect = fillObj.GetComponent<RectTransform>();
            fillRect.anchorMin = new Vector2(0f, 0f);
            fillRect.anchorMax = new Vector2(1f, 1f);
            fillRect.pivot = new Vector2(0f, 0.5f);
            fillRect.offsetMin = new Vector2(2f, 2f);
            fillRect.offsetMax = new Vector2(-2f, -2f);

            // Label showing "Name HP/MaxHP"
            var labelObj = new GameObject("Label");
            labelObj.transform.SetParent(canvasObj.transform, false);
            _label = labelObj.AddComponent<Text>();
            _label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            _label.fontSize = 14;
            _label.alignment = TextAnchor.MiddleCenter;
            _label.color = Color.white;
            _label.raycastTarget = false;
            var labelRect = labelObj.GetComponent<RectTransform>();
            labelRect.anchorMin = new Vector2(0f, 1f);
            labelRect.anchorMax = new Vector2(1f, 1f);
            labelRect.pivot = new Vector2(0.5f, 0f);
            labelRect.sizeDelta = new Vector2(_barWidth, 18f);
            labelRect.anchoredPosition = new Vector2(0f, 0f);
        }

        void LateUpdate()
        {
            if (_fighter == null) return;

            UpdateBar();

            // Billboard: always face the camera
            if (_canvas != null && Camera.main != null)
            {
                _canvas.transform.LookAt(
                    _canvas.transform.position + Camera.main.transform.rotation * Vector3.forward,
                    Camera.main.transform.rotation * Vector3.up);
            }
        }

        void UpdateBar()
        {
            if (_fighter == null || _barFill == null) return;

            float fraction = _fighter.HealthFraction;

            // Scale fill
            _barFill.fillAmount = fraction;

            // Color: green → yellow → red
            if (fraction > 0.5f)
                _barFill.color = Color.Lerp(new Color(1f, 0.85f, 0f), Color.green, (fraction - 0.5f) * 2f);
            else
                _barFill.color = Color.Lerp(Color.red, new Color(1f, 0.85f, 0f), fraction * 2f);

            // Update label
            if (_label != null)
            {
                string name = gameObject.name;
                string status = _fighter.IsDead ? " [DEAD]" : "";
                _label.text = $"{name}  {_fighter.Health:F0}/{_fighter.MaxHealth:F0}{status}";
            }
        }
    }
}
