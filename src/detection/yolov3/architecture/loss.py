import tensorflow as tf
import numpy as np

from src.detection.yolov3 import utils

"""
The implementation of the YOLO loss is inspired 
by the implementation of YunYang1994 published under the MIT license:
YunYang1994. Tensorflow-yolov3 [online]. GitHub, 2020 [cit. 2020-8-10].
Available at: https://github.com/YunYang1994/tensorflow-yolov3
"""
class YoloLoss(tf.keras.losses.Loss):

    def __init__(self, model_input_image_size, ignore_thresh=.5, name='yolo_loss'):
        """

        Parameters
        ----------
        model_input_image_size : TYPE
            DESCRIPTION.
        ignore_thresh : TYPE, optional
            DESCRIPTION. The default is .5.
        name : TYPE, optional
            DESCRIPTION. The default is 'yolo_loss'.

        Returns
        -------
        None.

        """
        super(YoloLoss, self).__init__(name=name)
        self.model_input_image_size = model_input_image_size  # (416, 416, 1)
        self.ignore_thresh = ignore_thresh
        return

    def call(self, y_true, y_pred):
        """
            Computes loss for YOLO network used in object detection.
            
            It doesn't include calculation of class predictions, since a single class is being predicted 
            and confidence is all that is required.
            
            Neither y_true and y_pred should contain class predictions.
        
        Parameters
        ----------
        y_true : 5D array
            True bounding boxes and class labels.
            Shape is (batch_size, grid_size, grid_size, anchors_per_grid_box, 5).
        y_pred : 5D array
            Prediction of bounding boxes and class labels.
            Shape is (batch_size, grid_size, grid_size, anchors_per_grid_box, 6).
            The last dimension also contains raw confidence.(tf.exp(box_shapes) * self.anchors) * stride
            
        Returns
        -------
        tf.Tensor
            Loss computed for bounding boxes and the confidence whether it contains an object.
            It is used in a YOLO network in object detection.
        """

        pred_xywh = y_pred[..., 0:4]
        raw_conf = y_pred[..., 5:6]

        true_xywh = y_true[..., 0:4]
        true_conf = y_true[..., 4:5]

        bbox_loss = self.iou_loss(true_conf, pred_xywh, true_xywh)
        conf_loss = self.confidence_loss(raw_conf, true_conf, pred_xywh, true_xywh)

        # There is no loss for class labels, since there is a single class
        # and confidence score represenets that class
        return bbox_loss + conf_loss

    def iou_loss(self, true_conf, pred_xywh, true_xywh):
        input_size = tf.cast(self.model_input_image_size[0], tf.float32)

        # Big boxes will generaly have greater IOU than small boxes.
        # We need to compensate for the different box sizes, 
        # so that the model is trained equally for small boxes and big boxes.
        bbox_loss_scale = 2.0 - true_xywh[..., 2:3] * true_xywh[..., 3:4] / (input_size ** 2)
        iou = utils.tensorflow_bbox_iou(pred_xywh[:, :, :, :, np.newaxis, :], true_xywh[:, :, :, :, np.newaxis, :])

        # If IOU = 0, then the boxes don't overlap - the worst result.
        # If IOU = 1, then the boxes overlap exactly - the best result.
        # Multiplied by true_conf -> the iou loss is calculated only for
        # true boxes.
        iou_loss = true_conf * bbox_loss_scale * (1 - iou)
        # Loss for each sample in the batch
        # iou_loss = tf.reduce_sum(iou_loss, axis=[1, 2, 3, 4])
        # Loss for the batch as a whole
        # iou_loss = tf.reduce_mean(iou_loss)
        return iou_loss

    def confidence_loss(self, raw_conf, true_conf, pred_xywh, true_xywh):
        bboxes_mask = true_conf
        bboxes_mask = tf.cast(bboxes_mask, dtype=tf.bool)
        bboxes = tf.boolean_mask(true_xywh, bboxes_mask[..., 0])

        iou = utils.tensorflow_bbox_iou(pred_xywh[:, :, :, :, np.newaxis, :], bboxes)
        # max_iou.shape for example (16, 26, 26, 3, 1)
        max_iou = tf.expand_dims(tf.reduce_max(iou, axis=-1), axis=-1)

        """
        zeros = tf.cast(tf.zeros_like(iou),dtype=tf.bool)
        ones = tf.cast(tf.ones_like(iou),dtype=tf.bool)
        loc = tf.where(iou>0.3, ones, zeros)
        result=tf.boolean_mask(iou, loc)
        tf.print("iou > 0.3", tf.shape(result), result)
        """

        """
        From YOLOv3 paper:
        'If the bounding box prior is not the best but does overlap a ground truth object by
        more than some threshold we ignore the prediction.'
        Meaning: true_conf is 0 if the grid cell is not responsible for that prediction,
        then the loss for that grid is computed only if the IoU is less than some 
        threshold. So we don't penalizes confidence of grid cells that do overlap
        the object by some margin.
        """

        loss_conf = tf.nn.sigmoid_cross_entropy_with_logits(labels=true_conf, logits=raw_conf)
        ignore_conf = (1.0 - true_conf) * tf.cast(max_iou < self.ignore_thresh, tf.float32)
        loss_conf = true_conf * loss_conf + ignore_conf * loss_conf
        return loss_conf
