import tensorflow as tf
import numpy as np
import math
import sys
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, '../utils'))
import tf_util

def placeholder_inputs(batch_size, num_point):
    pointclouds_pl = tf.placeholder(tf.float32, shape=(batch_size, num_point, 3))
    labels_pl = tf.placeholder(tf.int32, shape=(batch_size))
    return pointclouds_pl, labels_pl


def get_model(point_cloud, is_training, bn_decay=None, gridcell_num=500, per_num=10):
    """ Classification PointNet, input is BxNx3, output Bx40 """
    batch_size = point_cloud.get_shape()[0].value
    num_point = point_cloud.get_shape()[1].value
    end_points = {}
    point_cloud = tf.reshape(point_cloud, [-1, 3]) 
    net = tf_util.fully_connected(point_cloud, gridcell_num*per_num, bn=False, is_training=is_training,
                                  scope='grid_w', bn_decay=bn_decay, stddev=0.3, use_xavier=False)
    
    net = tf.exp(tf.complex(.0, net))

    c = tf_util._variable_with_weight_decay('c',
                                shape=[gridcell_num, per_num],
                                use_xavier=False,
                                stddev=0.1,
                                wd=0.0)
    net = tf.reshape(net, [batch_size * num_point, gridcell_num, per_num]) * tf.complex(c, .0)  
    net = tf.reduce_sum(net, axis=2)
    code = tf.reduce_mean( tf.reshape(net, [-1, num_point, gridcell_num]), axis=1)
    end_points['code'] = code
    net = tf.concat([tf.real(net), tf.imag(net)], axis=1)
    net = tf.reduce_mean( tf.reshape(net, [-1, num_point, 2*gridcell_num]), axis=1)

    # MLP on global point cloud vector
    #net = tf.reshape(net, [batch_size, -1])
    net = tf_util.fully_connected(net, 512, bn=False, is_training=is_training,
                                  scope='fc1', bn_decay=bn_decay)
    net = tf_util.fully_connected(net, 256, bn=False, is_training=is_training,
                                  scope='fc2', bn_decay=bn_decay)
    net = tf_util.dropout(net, keep_prob=0.7, is_training=is_training,
                          scope='dp1')
    net = tf_util.fully_connected(net, 40, activation_fn=None, scope='fc3')

    return net, end_points


def get_loss(pred, label, end_points, wb=1e0):
    """ pred: B*NUM_CLASSES,
        label: B, """
    code = end_points['code']
    batch_size = label.get_shape()[0].value
    #print(label.shape, batch_size, label.get_shape()[0], code.shape)
    codex = tf.tile( tf.expand_dims(code, axis=1), [1, batch_size, 1]) 
    codey = tf.tile( tf.expand_dims(code, axis=0), [batch_size, 1, 1])
    A = tf.square( tf_util._variable_on_cpu('A', [1], tf.constant_initializer(2.0)) )
    tmp = A * tf.reduce_sum(tf.real(codex * codey), axis=-1 )
    p_martix = tf.nn.softmax( tmp )
    
    #print(label.shape, batch_size)
    labelx = tf.tile( tf.expand_dims(label, axis=1), [1, batch_size]) 
    labely = tf.tile( tf.expand_dims(label, axis=0), [batch_size, 1])
    error_martix =  1 - tf.cast(tf.equal(labelx, labely), tf.int32)
    error_martix = tf.cast(error_martix, tf.float32)

    loss_re = tf.reduce_mean(tf.reduce_sum( p_martix * error_martix, axis=1) )

    loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=pred, labels=label)
    classify_loss = tf.reduce_mean(loss)
    tf.summary.scalar('classify loss', classify_loss)
    tf.summary.scalar('kernel loss', loss_re)
    return classify_loss + wb*loss_re


if __name__=='__main__':
    with tf.Graph().as_default():
        inputs = tf.zeros((32,1024,3))
        outputs = get_model(inputs, tf.constant(True))
        print(outputs)
