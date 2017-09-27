"""Functions for decoding model components to get loss and span probabilities.
"""

import tensorflow as tf

from model.tf_util import *
from model.rnn_util import *

def decode_answer_pointer_boundary(options, batch_size, keep_prob, spans,
        attention_outputs):
    with tf.variable_scope("answer_pointer"):
        V = tf.get_variable("V", shape=[2 * options.rnn_size,
                options.rnn_size])
        Wa_h = tf.get_variable("Wa_h", shape=[options.rnn_size,
                options.rnn_size])
        v = tf.get_variable("v", shape=[options.rnn_size])
        answer_lstm_cell = create_multi_rnn_cell(options, "answer_lstm",
                keep_prob)
    zeros = tf.zeros([batch_size, options.rnn_size])
    answer_pointer_state = (zeros,) * options.num_rnn_layers
    loss = tf.constant(0.0, dtype=tf.float32)
    start_span_probs = None
    end_span_probs = None
    max_len = tf.reshape(tf.tile(tf.constant([options.max_ctx_length - 1]),
                [batch_size]), [batch_size])
    VHr = multiply_3d_and_2d_tensor(attention_outputs, V) # size = [batch_size, max_ctx_length, rnn_size]
    v_reshaped = tf.reshape(v, [1, -1, 1]) # size = [1, rnn_size, 1]
    for z in range(2):
        Wa_h_ha = tf.constant(0.0, dtype=tf.float32)
        for s in answer_pointer_state:
            Wa_h_ha += tf.matmul(s, Wa_h) # size = [batch_size, rnn_size]
        inner_sum = Wa_h_ha
        inner_sum = VHr + tf.reshape(inner_sum, [batch_size, 1, options.rnn_size]) # size = [batch_size, max_ctx_length, rnn_size]
        F = tf.tanh(inner_sum) # size = [batch_size, max_ctx_length, rnn_size]
        v_tiled = tf.tile(v_reshaped, [batch_size, 1, 1]) # size = [batch_size, rnn_size, 1]
        vF = tf.reshape(tf.matmul(F, v_tiled), [batch_size, options.max_ctx_length]) # size = [batch_size, max_ctx_length]
        logits = vF # size = [batch_size, max_ctx_length]
        beta = tf.nn.softmax(logits)

        if z == 0:
            start_span_probs = beta
        else:
            end_span_probs = beta
        labels = tf.reshape(tf.minimum(spans[:,z], max_len), [batch_size])
        loss += tf.reduce_sum(
                tf.nn.sparse_softmax_cross_entropy_with_logits(
                    labels=labels, logits=logits)) \
               / tf.cast(batch_size, tf.float32)

        HrBeta = tf.matmul(tf.reshape(beta, [-1, 1, options.max_ctx_length]), attention_outputs)
        HrBeta = tf.reshape(HrBeta, [batch_size, 2 * options.rnn_size]) # size = [batch_size, 2 * rnn_size]
        with tf.variable_scope("answer_pointer_lstm", reuse=z > 0):
            _, answer_pointer_state = answer_lstm_cell(HrBeta, answer_pointer_state)
    return loss, start_span_probs, end_span_probs
