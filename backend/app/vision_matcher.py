import os
from typing import Optional, Tuple

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

def _resolve_path(image_url: Optional[str]) -> Optional[str]:
    """Map upload URL or path to real path under UPLOAD_DIR. Return None for remote/missing files."""
    if not image_url:
        return None
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return None
    filename = os.path.basename(image_url)
    if not filename:
        return None
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(path):
        return path
    return None

def calculate_dhash(image_path: str, hash_size: int = 8) -> Optional[str]:
    """Calculate Difference Hash (dHash) for perceptual image comparison at upload time or comparison time."""
    if not HAS_PIL or not image_path or not os.path.exists(image_path):
        return None
    try:
        with Image.open(image_path) as img:
            img = img.convert('L').resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
            difference = []
            for row in range(hash_size):
                for col in range(hash_size):
                    pixel_left = pixels[row * (hash_size + 1) + col]
                    pixel_right = pixels[row * (hash_size + 1) + col + 1]
                    difference.append(pixel_left > pixel_right)
            
            decimal_val = 0
            hex_str = []
            for i, val in enumerate(difference):
                if val:
                    decimal_val += 2 ** (i % 4)
                if i % 4 == 3:
                    hex_str.append(hex(decimal_val)[2:])
                    decimal_val = 0
            return "".join(hex_str)
    except Exception:
        return None

def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    if len(hash1) != len(hash2):
        return 64
    return sum(bin(int(c1, 16) ^ int(c2, 16)).count('1') for c1, c2 in zip(hash1, hash2))

def color_histogram_similarity(image_path1: str, image_path2: str) -> float:
    """Calculate HSV color histogram correlation score using OpenCV."""
    if not HAS_OPENCV or not os.path.exists(image_path1) or not os.path.exists(image_path2):
        return 50.0
    try:
        img1 = cv2.imread(image_path1)
        img2 = cv2.imread(image_path2)
        if img1 is None or img2 is None:
            return 50.0

        hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

        hist1 = cv2.calcHist([hsv1], [0, 1], None, [180, 256], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [180, 256], [0, 180, 0, 256])

        cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

        score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        normalized = max(0.0, min(100.0, (score + 1.0) / 2.0 * 100.0))
        return round(normalized, 2)
    except Exception:
        return 50.0

def calculate_image_similarity(
    image_url1: Optional[str],
    image_url2: Optional[str],
    hash1: Optional[str] = None,
    hash2: Optional[str] = None
) -> Tuple[float, bool]:
    """
    Calculate visual image similarity score (0.0 to 100.0) and is_estimated flag.
    Returns (score, is_estimated).
    """
    path1 = _resolve_path(image_url1)
    path2 = _resolve_path(image_url2)

    # Resolve hashes if not provided
    if not hash1 and path1:
        hash1 = calculate_dhash(path1)
    if not hash2 and path2:
        hash2 = calculate_dhash(path2)

    if hash1 and hash2:
        dist = hamming_distance(hash1, hash2)
        hash_sim = max(0.0, 100.0 - (dist / 64.0 * 100.0))
        
        if path1 and path2:
            color_sim = color_histogram_similarity(path1, path2)
        else:
            color_sim = hash_sim

        combined = round(0.6 * hash_sim + 0.4 * color_sim, 2)
        return (combined, False)

    # Fallback score when images cannot be resolved locally or hashed
    return (50.0, True)
