import glm

# Window configuration
DISPLAY_WIDTH = 900
DISPLAY_HEIGHT = 850
WINDOW_TITLE = "Gen 1 Starters"


# Camera settings
FOV = 50.0  # Field of view in degrees
NEAR_PLANE = 0.1
FAR_PLANE = 100.0

CAMERA_POS = glm.vec3(0, 40, 0)
CAMERA_TARGET = glm.vec3(0, 1, 0)
CAMERA_UP = glm.vec3(0, 1, 3)

# Texture unit bindings
TEXTURE_UNITS = {
    "BaseColor": 0,
    "Normal": 1,
    "Roughness": 2,
    "Alpha": 3,
    "Metallic": 4,
    "Emissive": 5
}
