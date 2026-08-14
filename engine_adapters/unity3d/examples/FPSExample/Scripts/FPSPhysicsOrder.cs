using System;
using UnityEngine;

namespace FPSExample
{
    internal static class FPSPhysicsOrder
    {
        public static Collider[] FindColliders()
        {
            Collider[] colliders = UnityEngine.Object.FindObjectsOfType<Collider>(true);
            Array.Sort(colliders, CompareColliders);
            return colliders;
        }

        public static void SortHits(RaycastHit[] hits)
        {
            Array.Sort(hits, CompareHits);
        }

        private static int CompareHits(RaycastHit left, RaycastHit right)
        {
            int result = left.distance.CompareTo(right.distance);
            return result != 0 ? result : CompareColliders(left.collider, right.collider);
        }

        private static int CompareColliders(Collider left, Collider right)
        {
            if (ReferenceEquals(left, right)) return 0;
            if (left == null) return 1;
            if (right == null) return -1;
            Bounds leftBounds = left.bounds;
            Bounds rightBounds = right.bounds;
            int result = leftBounds.center.x.CompareTo(rightBounds.center.x);
            if (result != 0) return result;
            result = leftBounds.center.y.CompareTo(rightBounds.center.y);
            if (result != 0) return result;
            result = leftBounds.center.z.CompareTo(rightBounds.center.z);
            if (result != 0) return result;
            result = leftBounds.size.x.CompareTo(rightBounds.size.x);
            if (result != 0) return result;
            result = leftBounds.size.y.CompareTo(rightBounds.size.y);
            if (result != 0) return result;
            result = leftBounds.size.z.CompareTo(rightBounds.size.z);
            return result != 0
                ? result
                : string.CompareOrdinal(StablePath(left.transform), StablePath(right.transform));
        }

        private static string StablePath(Transform item)
        {
            string path = "";
            for (Transform current = item; current != null; current = current.parent)
                path = current.GetSiblingIndex().ToString("D6") + ":" + current.name + "/" + path;
            return item.gameObject.scene.path + "/" + path;
        }
    }
}
