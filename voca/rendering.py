'''
Max-Planck-Gesellschaft zur Foerderung der Wissenschaften e.V. (MPG) is holder of all proprietary rights on this
computer program.

You can only use this computer program if you have closed a license agreement with MPG or you get the right to use
the computer program from someone who is authorized to grant you that right.

Any use of the computer program without a valid license is prohibited and liable to prosecution.

Copyright 2019 Max-Planck-Gesellschaft zur Foerderung der Wissenschaften e.V. (MPG). acting on behalf of its
Max Planck Institute for Intelligent Systems and the Max Planck Institute for Biological Cybernetics.
All rights reserved.

More information about VOCA is available at http://voca.is.tue.mpg.de.
For comments or questions, please email us at voca@tue.mpg.de
'''

from __future__ import division
import os
# os.environ['PYOPENGL_PLATFORM'] = 'osmesa' # Uncommnet this line while running remotely
import cv2
import pyrender
import trimesh
import tempfile
import numpy as np
import matplotlib as mpl
import matplotlib.cm as cm
from psbody.mesh import Mesh


def get_unit_factor(unit):
    if unit == 'mm':
        return 1000.0
    elif unit == 'cm':
        return 100.0
    elif unit == 'm':
        return 1.0
    else:
        raise ValueError('Unit not supported')


def rotate_camera_pose(scene, camera, k):
    # 初始摄像机位置
    camera_pose = np.array([[1, 0, 0, 0], [0, 1, 0, 0.7], [0, 0, 1, 1.0], [0, 0, 0, 1]])
    # 角度转弧度，45度
    theta = np.pi / 4
    # 绕y轴旋转的旋转矩阵
    # R_y = np.array([[np.cos(theta), 0, np.sin(theta), 0],
    #                 [0, 1, 0, 0],
    #                 [-np.sin(theta), 0, np.cos(theta), 0],
    #                 [0, 0, 0, 1]])

    R_y = np.array([
        [1, 0, 0, 0],
        [0, np.cos(theta), -np.sin(theta), 0],
        [0, np.sin(theta), np.cos(theta), 0],
        [0, 0, 0, 1]
    ])

    # 应用旋转
    for _ in range(k):
        camera_pose = R_y @ camera_pose

    camera_pose[:3, 3] = camera_pose[:3, 3] + np.array([0,0,2])
    # if k == 0:
    #     adjusted_camera_pose = np.array([[1, 0, 0, 0], [0, -1, 0, 1], [0, 0, -1, 0], [0, 0, 0, 1]])
    # elif k == 1:
    #     adjusted_camera_pose = np.array([[1, 0, 0, 0], [0, -1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]])
    # elif k == 2:
    #     adjusted_camera_pose = np.array([[1, 0, 0, 0], [0, 1, 0, 1], [0, 0, -1, 0], [0, 0, 0, 1]])
    # elif k == 3:
    #     adjusted_camera_pose = np.array([[1, 0, 0, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]])

    scene.add(camera, pose=camera_pose)

    light = pyrender.PointLight(color=np.array([1.0, 1.0, 1.0]) * 0.2, intensity=25)
    light_pose = np.eye(4)
    light_pose[:3, 3] = [0, -2, 2]
    for _ in range(k):
        light_pose = R_y @ light_pose
    scene.add(light, pose=light_pose)

    light_pose[:3, 3] = [0, 2, 2]
    for _ in range(k):
        light_pose = R_y @ light_pose
    scene.add(light, pose=light_pose)

    light_pose[:3, 3] = [-1, 1, 2]
    for _ in range(k):
        light_pose = R_y @ light_pose
    scene.add(light, pose=light_pose)

    # spot_l = pyrender.SpotLight(color=np.ones(3), intensity=15.0,
    #                             innerConeAngle=np.pi / 3, outerConeAngle=np.pi / 2)
    #
    # light_pose[:3, 3] = [-1, 2, 2]
    # for _ in range(k):
    #     light_pose = R_y @ light_pose
    # scene.add(spot_l, pose=light_pose)
    #
    # light_pose[:3, 3] = [1, 2, 2]
    # for _ in range(k):
    #     light_pose = R_y @ light_pose
    # scene.add(spot_l, pose=light_pose)


    return scene


def render_mesh_helper(mesh, t_center, rot=np.zeros(3), tex_img=None, v_colors=None,
                       errors=None, error_unit='m', min_dist_in_mm=0.0, max_dist_in_mm=3.0, z_offset=0, xmag=0.5,
                       y=0.7, z=1, camera='o', r=None, rotation_times=0):
    camera_params = {'c': np.array([0, 0]),
                     'k': np.array([-0.19816071, 0.92822711, 0, 0, 0]),
                     'f': np.array([5000, 5000])}

    frustum = {'near': 0.01, 'far': 3.0, 'height': 800, 'width': 800}

    mesh_copy = Mesh(mesh.v, mesh.f)
    mesh_copy.v[:] = cv2.Rodrigues(rot)[0].dot((mesh_copy.v - t_center).T).T + t_center

    texture_rendering = tex_img is not None and hasattr(mesh, 'vt') and hasattr(mesh, 'ft')
    if texture_rendering:
        intensity = 0.5
        tex = pyrender.Texture(source=tex_img, source_channels='RGB')
        material = pyrender.material.MetallicRoughnessMaterial(baseColorTexture=tex)

        # Workaround as pyrender requires number of vertices and uv coordinates to be the same
        temp_filename = '%s.obj' % next(tempfile._get_candidate_names())
        mesh.write_obj(temp_filename)
        tri_mesh = trimesh.load(temp_filename, process=False)
        try:
            os.remove(temp_filename)
        except:
            print('Failed deleting temporary file - %s' % temp_filename)
        render_mesh = pyrender.Mesh.from_trimesh(tri_mesh, material=material)
    elif errors is not None:
        intensity = 0.5
        unit_factor = get_unit_factor('mm') / get_unit_factor(error_unit)
        errors = unit_factor * errors

        norm = mpl.colors.Normalize(vmin=min_dist_in_mm, vmax=max_dist_in_mm)
        cmap = cm.get_cmap(name='jet')
        colormapper = cm.ScalarMappable(norm=norm, cmap=cmap)
        rgba_per_v = colormapper.to_rgba(errors)
        rgb_per_v = rgba_per_v[:, 0:3]
    elif v_colors is not None:
        intensity = 0.5
        rgb_per_v = v_colors
    else:
        intensity = 6.
        rgb_per_v = None

    color = np.array([0.3, 0.5, 0.55])

    if not texture_rendering:
        tri_mesh = trimesh.Trimesh(vertices=mesh_copy.v, faces=mesh_copy.f, vertex_colors=rgb_per_v)
        render_mesh = pyrender.Mesh.from_trimesh(tri_mesh,
                                                 smooth=True,
                                                 material=pyrender.MetallicRoughnessMaterial(
                                                     metallicFactor=0.05,
                                                     roughnessFactor=0.7,
                                                     alphaMode='OPAQUE',
                                                     baseColorFactor=(color[0], color[1], color[2], 1.0)
                                                 ))

    scene = pyrender.Scene(ambient_light=[.2, .2, .2], bg_color=[255, 255, 255])

    if camera == 'o':
        camera = pyrender.OrthographicCamera(xmag=xmag, ymag=xmag)
        # camera = pyrender.OrthographicCamera(xmag=xmag, ymag=xmag*1.8)
    elif camera == 'i':
        camera = pyrender.IntrinsicsCamera(fx=camera_params['f'][0],
                                           fy=camera_params['f'][1],
                                           cx=camera_params['c'][0],
                                           cy=camera_params['c'][1],
                                           znear=frustum['near'],
                                           zfar=frustum['far'])
    elif camera == 'y':
        camera = pyrender.PerspectiveCamera(yfov=(np.pi / 2.0))

    scene.add(render_mesh, pose=np.eye(4))

    scene = rotate_camera_pose(scene, camera, rotation_times)

    # scene.add(camera, pose=rotate_camera_pose(rotation_times))
    # scene.add(camera, pose=[[1, 0, 0, 0],
    #                         [0, 1, 0, y],  # 0.25
    #                         [0, 0, 1, z],  # 0.2
    #                         [0, 0, 0, 1]])


    angle = np.pi / 6.0
    # pos = camera_pose[:3,3]
    pos = np.array([0, 0.7, 2.0])
    # if False:
    #     light_color = np.array([1., 1., 1.])
    #     light = pyrender.DirectionalLight(color=light_color, intensity=intensity)
    #
    #     light_pose = np.eye(4)
    #     light_pose[:3, 3] = np.array([0, 0.7, 2.0])
    #     scene.add(light, pose=light_pose.copy())
    # else:
    #     light = pyrender.PointLight(color=np.array([1.0, 1.0, 1.0]) * 0.2, intensity=2)
    #     light_pose = np.eye(4)
    #     light_pose[:3, 3] = [0, -1, 1]
    #     scene.add(light, pose=light_pose)
    #
    #     light_pose[:3, 3] = [0, 1, 1]
    #     scene.add(light, pose=light_pose)
    #
    #     light_pose[:3, 3] = [-1, 1, 2]
    #     scene.add(light, pose=light_pose)
    #
    #     spot_l = pyrender.SpotLight(color=np.ones(3), intensity=15.0,
    #                                 innerConeAngle=np.pi / 3, outerConeAngle=np.pi / 2)
    #
    #     light_pose[:3, 3] = [-1, 2, 2]
    #     scene.add(spot_l, pose=light_pose)
    #
    #     light_pose[:3, 3] = [1, 2, 2]
    #     scene.add(spot_l, pose=light_pose)

    # light_pose[:3,3] = cv2.Rodrigues(np.array([angle, 0, 0]))[0].dot(pos)
    # scene.add(light, pose=light_pose.copy())
    #
    # light_pose[:3,3] = cv2.Rodrigues(np.array([-angle, 0, 0]))[0].dot(pos)
    # scene.add(light, pose=light_pose.copy())
    #
    # light_pose[:3,3] = cv2.Rodrigues(np.array([0, -angle, 0]))[0].dot(pos)
    # scene.add(light, pose=light_pose.copy())
    #
    # light_pose[:3,3] = cv2.Rodrigues(np.array([0, angle, 0]))[0].dot(pos)
    # scene.add(light, pose=light_pose.copy())

    # pyrender.Viewer(scene)

    flags = pyrender.RenderFlags.SKIP_CULL_FACES
    # try:
    # r = pyrender.OffscreenRenderer(viewport_width=frustum['width'], viewport_height=frustum['height'])
    color, _ = r.render(scene, flags=flags)
    # r.delete()
    # except:
    #     print('pyrender: Failed rendering frame')
    #     color = np.zeros((frustum['height'], frustum['width'], 3), dtype='uint8')

    return color[..., ::-1]
