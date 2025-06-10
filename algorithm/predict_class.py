import argparse
import multiprocessing as mp
import os
import uuid
import cv2
import numpy as np
from PIL import Image
from dense_platform_backend_main.algorithm.predictor import VisualizationDemo
from adet.config import get_cfg
import json



"""api接口开发预测函数封装"""

def setup_cfg(args):
    # load config from file and command-line arguments
    cfg = get_cfg()
    cfg.set_new_allowed(True)
    cfg.merge_from_file(args.config_file)
    cfg.merge_from_list(args.opts)
    # Set score_threshold for builtin models
    cfg.MODEL.RETINANET.SCORE_THRESH_TEST = args.confidence_threshold
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = args.confidence_threshold
    cfg.MODEL.FCOS.INFERENCE_TH_TEST = args.confidence_threshold
    cfg.MODEL.MEInst.INFERENCE_TH_TEST = args.confidence_threshold
    cfg.MODEL.PANOPTIC_FPN.COMBINE.INSTANCES_CONFIDENCE_THRESH = args.confidence_threshold
    cfg.freeze()
    return cfg

def get_parser():
    parser = argparse.ArgumentParser(description="Detectron2 Demo")
    parser.add_argument(
        "--config-file",
        default="/data/HZNU_ZWY/AdelaiDet/configs/BlendMask/R_101_3x.yaml",
        metavar="FILE",
        help="path to config file",
    )
    parser.add_argument("--webcam", action="store_true", help="Take inputs from webcam.")
    parser.add_argument("--video-input", help="Path to video file.")
    parser.add_argument(
        "--output",
        help="A file or directory to save output visualizations. "
             "If not given, will show output in an OpenCV window.",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.35,
        help="Minimum score for instance predictions to be shown",
    )
    parser.add_argument(
        "--opts",
        help="Modify config options using the command-line 'KEY VALUE' pairs",
        default=[],
        nargs=argparse.REMAINDER,
    )
    return parser

def predict(input_image=None):
    mp.set_start_method("spawn", force=True)
    args = get_parser().parse_args()
    args.input = input_image
    cfg = setup_cfg(args)

    demo = VisualizationDemo(cfg)

    img = cv2.cvtColor(args.input, cv2.COLOR_RGB2BGR) if args.input.shape[-1] == 3 else args.input
    predictions, visualized_output, data_json = demo.run_on_image(img)
    file_path = "/data/HZNU_ZWY/AdelaiDet/output/blendmask/data.json"
    image_id = str(uuid.uuid4())
    base_path = "/data/HZNU_ZWY/AdelaiDet/dense_platform_backend_main/storage/reports/Result_image/"
    output_image_path = os.path.join(base_path, f"{image_id}.jpg")
    pil_image = Image.fromarray(cv2.cvtColor(visualized_output.get_image(), cv2.COLOR_BGR2RGB))
    pil_image.save(output_image_path, "JPEG")
    with open(file_path, 'w') as json_file:
        json.dump(data_json, json_file, indent=4)

    return data_json,image_id
    # # 使用PIL库保存图像
    # output_image_path = "D:/Code_resource/AdelaiDet/demo/predict_dataset/predicted_image.jpg"
    # pil_image = Image.fromarray(cv2.cvtColor(visualized_output.get_image(), cv2.COLOR_BGR2RGB))
    # pil_image.save(output_image_path, "JPEG")
    #
    # # 可以选择使用matplotlib来展示图片
    # import matplotlib.pyplot as plt
    # image = cv2.imread(output_image_path)
    # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    #
    # plt.imshow(image)
    # plt.axis('off')  # 关闭坐标轴
    # plt.show()

# def predict_img():
#
#     contents = open("/home/HZNU_ZWY/1.jpg","rb").read()
#     image_np = np.asarray(bytearray(contents), dtype=np.uint8)
#     img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
#     data_json = predict(img)
#     print(data_json)
#
# if __name__ == '__main__':
#     contents = open("/data/HZNU_ZWY/AdelaiDet/demo/predicted_image.jpg", "rb").read()
#     image_np = np.asarray(bytearray(contents), dtype=np.uint8)
#     img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
#     data_json = predict(img)