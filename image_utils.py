import numpy as np
import torch
from torch.nn import functional as F
import ctypes
import sdl2


def get_texture_size(texture):
    w = ctypes.c_int()
    h = ctypes.c_int()
    sdl2.SDL_QueryTexture(texture, None, None, ctypes.byref(w), ctypes.byref(h))
    return w.value, h.value


def unpack_rgb444_image(buffer, image_shape):
    mask = (2 << 10) - 1
    img = np.frombuffer(buffer, dtype=np.uint32).reshape(*image_shape).byteswap()
    red = (img >> 20) & mask
    green = (img >> 10) & mask
    blue = (img) & mask
    unpacked_image = np.stack((red, green, blue)).astype(np.float32) / 1024.0
    return unpacked_image


def half_size_batch(batch):
    return F.interpolate(batch, scale_factor=0.5, mode="area")


def uyvy_to_rgb_batch(uyvy_images):
    # Convert the batch of images to float32
    uyvy_f32 = uyvy_images.to(torch.float32)

    # Handle the Y channel
    y_channel = uyvy_f32[:, :, :, 1].unsqueeze(
        1
    )  # Keep the Y channel in its own dimension
    y_channel = F.interpolate(y_channel, scale_factor=0.5, mode="area")

    # Handle the U channel
    u_channel = uyvy_f32[:, :, 0::2, 0].unsqueeze(1)
    h, w = (
        y_channel.shape[-2],
        y_channel.shape[-1],
    )  # Extract the new dimensions after Y interpolation
    u_channel = F.interpolate(u_channel, size=(h, w), mode="area")

    # Handle the V channel
    v_channel = uyvy_f32[:, :, 1::2, 0].unsqueeze(1)
    v_channel = F.interpolate(v_channel, size=(h, w), mode="area")

    # Normalize channels to [0,1] range
    y_channel /= 255.0
    u_channel /= 255.0
    v_channel /= 255.0

    # Recalculate R, G, B based on Y, U, V
    r = y_channel + 1.402 * (v_channel - 0.5)
    g = y_channel - 0.344136 * (u_channel - 0.5) - 0.714136 * (v_channel - 0.5)
    b = y_channel + 1.772 * (u_channel - 0.5)

    # Stack the channels and clamp the values
    rgb_images = torch.cat(
        (r, g, b), dim=1
    )  # Concatenate along the color channel dimension
    rgb_images = torch.clamp(rgb_images, 0.0, 1.0)

    return rgb_images
