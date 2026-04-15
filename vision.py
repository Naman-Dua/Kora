import cv2

def scan_for_master():
    cap = cv2.VideoCapture(0)
    # Uses the built-in Haar Cascade for face detection
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    print("Vision: Scanning for Master...")
    for _ in range(40): # Scan for about 4 seconds
        ret, frame = cap.read()
        if not ret: break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        if len(faces) > 0:
            cap.release()
            cv2.destroyAllWindows()
            return True
            
    cap.release()
    cv2.destroyAllWindows()
    return False