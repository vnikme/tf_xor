#!/usr/bin/python
# coding: utf-8

import sys, base64, json, random
import tensorflow as tf
import numpy as np


START, STOP = 0, 1

def read_data(path, max_length):
    data, targets = [], []
    for line in open(path, "rt"):
        js = json.loads(base64.b64decode(line))
        if "correctedText" not in js:
            continue
        data.append(js["correctedText"])
        #if len(data) > 20:
        #    break
    data = filter(lambda x: len(x) <= max_length - 1, data)
    n = len(data)
    chars = ["start", "stop"] + list(set(''.join(data)))
    codes = {}
    for i in xrange(2, len(chars)):
        codes[chars[i]] = i
    for i in xrange(n):
        idx = [START]
        for j in xrange(len(data[i])):
            idx.append(codes[data[i][j]])
        while len(idx) < max_length:
            idx.append(STOP)
        data[i] = idx
        targets.append(idx[1:] + [STOP])
    print(len(data))
    return np.array(data), np.array(targets), chars, codes


def feed_zero_encoder_state(encoder_state_inputs, batch_size, hidden_size):
    result = {}
    for c in encoder_state_inputs:
        result[c] = np.zeros((batch_size, hidden_size))
    return result


def choose_random(distr, verbose):
    cs = np.cumsum(distr)
    s = np.sum(distr)
    if verbose:
        print("%s" % (" ".join(map(lambda t: "%.2f" % t, distr))))
    k = int(np.searchsorted(cs, np.random.rand(1) * s))
    return min(max(k, 0), len(distr) - 1)


def sample1(sess, encoder_one_output_projected, encoder_one_state, encoder_inputs, encoder_state_inputs, hidden_size, max_time, max_len, vocabulary, c):
    feed = feed_zero_encoder_state(encoder_state_inputs, 1, hidden_size)
    result = ""
    for i in xrange(max_len):
        feed[encoder_inputs] = [[c] + [STOP for _ in xrange(max_time - 1)]]
        output, state = sess.run([encoder_one_output_projected, encoder_one_state], feed_dict = feed)
        feed = {}
        for j in xrange(len(encoder_state_inputs)):
            feed[encoder_state_inputs[j]] = state[j]
        c = choose_random(output[0], i == 0)
        if c == STOP:
            break
        result += vocabulary[c]
    return result


def main():
    with tf.Session() as sess:
        max_time = 64
        data, targets, vocabulary, codes = read_data(sys.argv[1], max_time)
        batch_size, hidden_size, number_of_layers, vocabulary_size = 8, 128, 4, len(vocabulary)

        def basic_cell(k, prefix):
            return tf.nn.rnn_cell.GRUCell(hidden_size, name = prefix + str(k))

        encoder_inputs = tf.placeholder(tf.int32, (None, max_time))
        encoder_inputs_oh = tf.transpose(tf.one_hot(encoder_inputs, vocabulary_size, tf.to_double(1.0), dtype = tf.float64, axis = -1), [1, 0, 2])
        #print encoder_inputs.shape, encoder_inputs_oh.shape
        encoder_state_inputs = []
        for i in xrange(number_of_layers):
            encoder_state_inputs.append(tf.placeholder(tf.float64, [None, hidden_size]))
        encoder_state_input = tuple(encoder_state_inputs)

        encoder_targets = tf.placeholder(tf.int32, (None, max_time))
        encoder_targets_oh = tf.transpose(tf.one_hot(encoder_targets, vocabulary_size, tf.to_double(1.0), dtype = tf.float64, axis = -1), [1, 0, 2])

        encoder_base_cells = [basic_cell(i, "encoder_") for i in range(number_of_layers)]
        encoder_cell = tf.nn.rnn_cell.MultiRNNCell(encoder_base_cells)

        encoder_w = tf.get_variable("encoder_w", (hidden_size, vocabulary_size), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64)
        encoder_b = tf.get_variable("encoder_b", (vocabulary_size), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64) 

        state, encoder_loss, encoder_one_output, encoder_one_state = encoder_state_input, None, None, None
        for i in xrange(max_time):
            output, state = encoder_cell(encoder_inputs_oh[i], state)
            output_projected = tf.add(tf.matmul(output, encoder_w), encoder_b)
            loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits_v2(logits = output_projected, labels = encoder_targets_oh[i])) / max_time
            if i == 0:
                encoder_one_output_projected = tf.nn.softmax(output_projected)
                encoder_one_output, encoder_one_state = output, state
                encoder_loss = loss
            else:
                encoder_loss += loss
        encoder_final_state = tf.concat(state, axis = 1)

        encoder_optimizer = tf.train.AdamOptimizer(0.0001).minimize(encoder_loss)

        sess.run(tf.global_variables_initializer())

        for i in xrange(10000000):
            feed = feed_zero_encoder_state(encoder_state_inputs, batch_size, hidden_size)
            r = random.randint(0, data.shape[0] - batch_size)
            feed[encoder_inputs] = data[r : r + batch_size]
            feed[encoder_targets] = targets[r : r + batch_size]
            _, l = sess.run([encoder_optimizer, encoder_loss], feed_dict = feed)
            if i % 100 == 0:
                print "%.5f" % (l)
                print sample1(sess, encoder_one_output_projected, encoder_one_state, encoder_inputs, encoder_state_inputs, hidden_size, max_time, 100, vocabulary, START).encode("utf-8")
                print
            sys.stdout.flush()
        exit(1)









        generator_outputs, generator_one_output, generator_one_state = [], None, None
        for i in xrange(max_time):
            output, state = generator_cell(output, state)
            if i == 0:
                generator_one_output, generator_one_state = output, state
            generator_outputs.append(tf.add(tf.matmul(output, generator_w), generator_b))
        generator_vars = generator_cell.trainable_variables + [generator_w, generator_b]


        exit(1)

        generator_c_states, generator_h_states, generator_state_input = [], [], []
        for i in xrange(number_of_layers):
            generator_c_states.append(tf.placeholder(tf.float64, [None, hidden_size]))
            generator_h_states.append(tf.placeholder(tf.float64, [None, hidden_size]))
            generator_state_input.append(tf.nn.rnn_cell.LSTMStateTuple(c = generator_c_states[-1], h = generator_h_states[-1]))
        generator_state_input = tuple(generator_state_input)
        generator_base_cells = [lstm_cell(i, "generator_") for i in range(number_of_layers)]
        generator_cell = tf.nn.rnn_cell.MultiRNNCell(generator_base_cells)
        output, state = generator_input, generator_state_input
        generator_w = tf.get_variable("generator_w", (hidden_size, vocabulary_size), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64)
        generator_b = tf.get_variable("generator_b", (vocabulary_size), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64)
        generator_outputs, generator_one_output, generator_one_state = [], None, None
        for i in xrange(max_time):
            output, state = generator_cell(output, state)
            if i == 0:
                generator_one_output, generator_one_state = output, state
            generator_outputs.append(tf.add(tf.matmul(output, generator_w), generator_b))
        generator_vars = generator_cell.trainable_variables + [generator_w, generator_b]

        discriminator_input = tf.placeholder(tf.int32, (batch_size, max_time))
        real_input = tf.transpose(tf.one_hot(discriminator_input, vocabulary_size, tf.to_double(1.0), dtype = tf.float64, axis = -1), [1, 0, 2])
        discriminator_base_cells = [lstm_cell(i, "discriminator_") for i in range(number_of_layers)]
        discriminator_cell = tf.nn.rnn_cell.MultiRNNCell(discriminator_base_cells)
        discriminator_w1 = tf.get_variable("discriminator_w1", (vocabulary_size, hidden_size), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64)
        discriminator_b1 = tf.get_variable("discriminator_b1", (hidden_size), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64)
        discriminator_w2 = tf.get_variable("discriminator_w2", (number_of_layers * hidden_size, 1), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64)
        discriminator_b2 = tf.get_variable("discriminator_b2", (1), initializer = tf.random_normal_initializer(0.0, 1.0), dtype = tf.float64)
        discriminator_real_state = discriminator_cell.zero_state(batch_size, tf.float64)
        discriminator_fake_state = discriminator_cell.zero_state(batch_size, tf.float64)
        for i in xrange(max_time):
            _, discriminator_real_state = discriminator_cell(tf.add(tf.matmul(real_input[i], discriminator_w1), discriminator_b1), discriminator_real_state)
            _, discriminator_fake_state = discriminator_cell(tf.add(tf.matmul(generator_outputs[i], discriminator_w1), discriminator_b1), discriminator_fake_state)
        discriminator_vars = discriminator_cell.trainable_variables + [discriminator_w1, discriminator_b1, discriminator_w2, discriminator_b2]
        #for var in tf.trainable_variables():
        #    print var.name
        #exit(1)

        def reshape_discriminator_state(state):
            result = [state[i][0] for i in xrange(number_of_layers)]
            result = tf.stack(result, axis = 1)
            result = tf.reshape(result, [batch_size, number_of_layers * hidden_size])
            result = tf.add(tf.matmul(result, discriminator_w2), discriminator_b2)
            return result

        discriminator_real_state = reshape_discriminator_state(discriminator_real_state)
        discriminator_fake_state = reshape_discriminator_state(discriminator_fake_state)

        char_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits = generator_outputs, labels = tf.one_hot(tf.transpose(discriminator_input, [1, 0]), vocabulary_size, tf.to_double(1.0), dtype = tf.float64, axis = -1)))

        real_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits = discriminator_real_state, labels = tf.ones_like(discriminator_real_state)))
        fake_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits = discriminator_fake_state, labels = tf.zeros_like(discriminator_fake_state)))
        generator_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits = discriminator_fake_state, labels = tf.ones_like(discriminator_fake_state))) + char_loss
        discriminator_loss = real_loss + fake_loss

        generator_optimizer = tf.train.AdamOptimizer(0.0001).minimize(generator_loss, var_list = generator_vars)
        discriminator_optimizer = tf.train.AdamOptimizer(0.0001).minimize(discriminator_loss, var_list = discriminator_vars)
        #generator_optimizer = tf.train.GradientDescentOptimizer(0.001).minimize(generator_loss, var_list = generator_vars)
        #discriminator_optimizer = tf.train.GradientDescentOptimizer(0.001).minimize(discriminator_loss, var_list = discriminator_vars)
        #generator_optimizer = tf.train.AdadeltaOptimizer(0.001).minimize(generator_loss, var_list = generator_vars)
        #discriminator_optimizer = tf.train.AdadeltaOptimizer(0.001).minimize(discriminator_loss, var_list = discriminator_vars)

    sess.run(tf.global_variables_initializer())

    for i in xrange(10000000):
        feed = feed_random_generator_state(generator_c_states, generator_h_states, batch_size, hidden_size)
        feed[generator_input] = np.zeros((batch_size, hidden_size))
        r = random.randint(0, data.shape[0] - 1 - batch_size)
        feed[discriminator_input] = data[r : r + batch_size]
        _, dl, gl = sess.run([generator_optimizer, discriminator_loss, generator_loss], feed_dict = feed)
        if dl > 0.001:
            sess.run(discriminator_optimizer, feed_dict = feed)
        print "%.5f\t%.5f" % (dl, gl)
        if i % 100 == 0:
            print sample1(sess, generator_outputs, generator_input, generator_c_states, generator_h_states, hidden_size, vocabulary).encode("utf-8")
            print
        sys.stdout.flush()


if __name__ == "__main__":
    main()

