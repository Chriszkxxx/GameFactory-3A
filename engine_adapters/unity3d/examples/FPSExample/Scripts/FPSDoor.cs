using System;
using System.Collections.Generic;
using UnityEngine;

namespace FPSExample
{
    [DisallowMultipleComponent]
    public sealed class FPSDoor : MonoBehaviour
    {
        [SerializeField] private float openDistance = 1.45f;
        [SerializeField] private float openSpeed = 3.5f;

        private Transform[] panels = Array.Empty<Transform>();
        private Vector3[] closedPositions = Array.Empty<Vector3>();
        private Vector3[] openPositions = Array.Empty<Vector3>();

        public bool IsOpen { get; private set; }
        public bool IsConfigured => panels.Length > 0;

        public event Action<FPSDoor> StateChanged;

        public bool ConfigureFromPrefab()
        {
            var uniquePanels = new HashSet<Transform>();
            foreach (BoxCollider collider in GetComponentsInChildren<BoxCollider>(true))
            {
                if (collider == null || collider.isTrigger)
                    continue;
                Vector3 size = collider.bounds.size;
                if (size.y < 1.5f || Mathf.Max(size.x, size.z) < 0.5f ||
                    Mathf.Min(size.x, size.z) > 0.75f)
                    continue;
                uniquePanels.Add(collider.transform);
            }

            var sorted = new List<Transform>(uniquePanels);
            sorted.Sort((left, right) =>
                transform.InverseTransformPoint(left.position).x.CompareTo(
                    transform.InverseTransformPoint(right.position).x));
            if (sorted.Count > 2)
                sorted = sorted.GetRange(0, 2);
            if (sorted.Count == 0)
            {
                enabled = false;
                return false;
            }

            panels = sorted.ToArray();
            closedPositions = new Vector3[panels.Length];
            openPositions = new Vector3[panels.Length];
            for (int index = 0; index < panels.Length; index++)
            {
                Transform panel = panels[index];
                closedPositions[index] = panel.localPosition;
                float side = index == 0 ? -1f : 1f;
                Vector3 worldDirection = transform.right * side;
                Vector3 localDirection = panel.parent != null
                    ? panel.parent.InverseTransformDirection(worldDirection).normalized
                    : worldDirection.normalized;
                openPositions[index] = closedPositions[index] + localDirection * openDistance;
            }
            return true;
        }

        public void Toggle()
        {
            SetOpen(!IsOpen, false);
        }

        public void SetOpen(bool open, bool immediate)
        {
            if (!IsConfigured)
                return;
            IsOpen = open;
            if (immediate)
            {
                for (int index = 0; index < panels.Length; index++)
                    if (panels[index] != null)
                        panels[index].localPosition = open
                            ? openPositions[index]
                            : closedPositions[index];
            }
            Debug.Log("[FPS_DOOR] " + name + " open=" + IsOpen);
            StateChanged?.Invoke(this);
        }

        private void Update()
        {
            for (int index = 0; index < panels.Length; index++)
            {
                if (panels[index] == null)
                    continue;
                Vector3 target = IsOpen ? openPositions[index] : closedPositions[index];
                panels[index].localPosition = Vector3.MoveTowards(
                    panels[index].localPosition,
                    target,
                    Mathf.Max(0f, openSpeed) * Time.deltaTime);
            }
        }
    }
}
