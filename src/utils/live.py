import matplotlib.pyplot as plt
import numpy as np
import pyrealsense2 as rs

from src.utils.plots import _plot_depth_image_live


def generate_live_images():
    pipe = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, 640, 480)
    pipe.start(cfg)
    try:
        while True:
            frameset = pipe.wait_for_frames()
            depth_frame = frameset.get_depth_frame()
            depth_image = np.array(depth_frame.get_data())
            depth_image = depth_image[..., np.newaxis]

            yield depth_image

    finally:
        pipe.stop()


def print_live_images(num=None):
    generator = generate_live_images()

    fig, ax = plt.subplots()
    i = 0
    while True:
        if i == num:
            break
        i += 1

        depth_image = next(generator)
        _plot_depth_image_live(ax, depth_image)


def intrinsic_parameters():
    """
    Retrieves camera's parameters for a depth stream of
    shape (640, 480).

    Returns
    -------
    intrinsics
    max_distance
    """
    pipe = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, 640, 480)
    profile = pipe.start(cfg)
    stream = profile.get_stream(rs.stream.depth).as_video_stream_profile()
    intrinsics = stream.get_intrinsics()

    depth_sensor = profile.get_device().first_depth_sensor()
    max_distance = depth_sensor.get_option(rs.option.max_distance)
    """
    fx = fy = 476.0068054199219
    ppx, ppy = 313.6830139, 242.7547302
    depth_units = 0.00012498664727900177
    => 1 mm / depth_units = 8.00085466544
    
    D415
    [ 640x480  p[313.79 238.076]  f[592.138 592.138]  Brown Conrady [0 0 0 0 0] ]
    """
    pipe.stop()
    return intrinsics, max_distance


if __name__ == '__main__':
    # intrinsic_parameters()
    print_live_images()
