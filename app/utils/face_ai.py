import os
import warnings
import logging

# Membungkam log bawaan TensorFlow (C++) dan oneDNN agar terminal bersih
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_VLOG_LEVEL'] = '3'

# Mengabaikan peringatan Deprecated dari library tf-keras
warnings.filterwarnings("ignore")

try:
    import tensorflow as tf
    tf.get_logger().setLevel(logging.ERROR)
    tf.autograph.set_verbosity(0)
except ImportError:
    pass

from fastapi import HTTPException
from deepface import DeepFace

def extract_face_vector(image_path: str) -> list[float]:
    """
    Mengekstrak embedding wajah 512 dimensi menggunakan Facenet512.
    
    Args:
        image_path: Path lokal sementara dari file gambar wajah.
        
    Returns:
        list[float]: Vektor representasi wajah (512 dimensi).
    """
    try:
        results = DeepFace.represent(
            img_path=image_path,
            model_name='Facenet512',
            enforce_detection=True
        )
        
        if not results:
            raise ValueError("Wajah tidak ditemukan dalam gambar.")
            
        embedding = results[0]["embedding"]
        return embedding
        
    except ValueError as ve:
        # Error dilempar oleh DeepFace saat wajah tidak terdeteksi
        print(f"DEBUG AI ERROR: {str(ve)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Gagal memproses wajah: {str(ve)}"
        )
    except Exception as e:
        print(f"DEBUG AI ERROR: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Gagal memproses wajah: {str(e)}"
        )
