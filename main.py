import scipy.io as spio
from tree import TreeNode
import math
import sys
import random
import numpy as np
import multiprocessing
import collections
from functools import partial, reduce


def main():
    clean_data = 'Data/cleandata_students.mat'
    noisy_data = 'Data/noisydata_students.mat'
    total_attributes = 45
    number_of_emotions = 6
    number_of_trees = number_of_emotions
    k_folds = 10
    randomise = False

    #create k_folds threads, 1 for each iteration
    pool = multiprocessing.Pool(k_folds)

    # Extract data from the file
    mat = spio.loadmat(clean_data, squeeze_me=True)
    x_input = list(mat['x'])
    y_input = list(mat['y'])

    #shuffle data
    x, y = shuffle_data(x_input, y_input)

    #Create attribute list
    attributes = list(range(1, total_attributes + 1))

    #train trees and get test results
    train = partial(train_test, x=x, y=y, attributes=attributes[:], number_of_trees=number_of_trees, k_folds=k_folds, randomise=randomise)
    results = pool.map(train, range(k_folds))

    #Create confusion matrix from the results
    percentages = list(map(lambda tup: tup[1], results))
    mats = list(map(lambda tup: tup[0], results))
    confusion_matrix = [[0 for _ in range(number_of_trees)] for _ in range(number_of_trees)]
    for mat in mats:
        for i in range(number_of_trees):
            for j in range(number_of_trees):
                confusion_matrix[i][j] += mat[i][j]

    for i in range(number_of_trees):
        for j in range(number_of_trees):
            confusion_matrix[i][j] /= k_folds

    print(confusion_matrix)
    print(percentages)
    print(np.mean(percentages))

def shuffle_data(a, b):
    combined = list(zip(a, b))
    random.shuffle(combined)
    a[:], b[:] = zip(*combined)
    return a, b

def train_test(i, x, y, attributes, number_of_trees, k_folds, randomise):
    test_data_input = []
    test_data_output = []
    training_data_input = []
    training_data_output = []
    validation_data_input = []
    validation_data_output = []
    for j in range(len(x)):
        if j % k_folds == i:
            # One fold data used for tests
            test_data_input.append(x[j])
            test_data_output.append(y[j])
        elif j % k_folds == (i+1) % k_folds:
            # One fold data used for validation
            validation_data_input.append(x[j])
            validation_data_output.append(y[j])
        else:
            # Remaining eight fold data used for training
            training_data_input.append(x[j])
            training_data_output.append(y[j])
    tree_priority = [0] * number_of_trees

    if not randomise:
        #if not using random strategy get tree_priority from validation data
        unvalidated_trees = train_trees(number_of_trees, attributes[:], training_data_input, training_data_output)
        tree_priority = get_tree_priority(unvalidated_trees, validation_data_input, validation_data_output)


    #train final trees and get predictions from test data
    trees = train_trees(number_of_trees, attributes[:], training_data_input, training_data_output)

    change = 0
    while (change <= 0.001):
        new_trees = trees[:]
        before = np.mean(get_tree_priority(new_trees, validation_data_input, validation_data_output))
        for i in range(len(new_trees)):
            new_trees[i].prune_tree(0, 15)
        change = np.mean(get_tree_priority(new_trees, validation_data_input, validation_data_output)) - before
    print ("change ", change * 100)
    # dump_tree("before " + str(i), trees[0])
    # trees[0].prune_tree(0)
    # dump_tree("after "  + str(i), trees[0])
    predictions = get_predictions(trees, test_data_input, tree_priority, randomise)
    confusion_mat = [[0 for _ in range(number_of_trees)] for _ in range(number_of_trees)]
    # get confusion matrix
    for i in range(len(predictions)):
        confusion_mat[test_data_output[i]-1][predictions[i]-1] += 1
    return confusion_mat, evaluate_results(predictions, test_data_output)


#compare predictions with actual results
def evaluate_results(predictions, actual_outputs):
    correct_cases = 0
    incorrect_cases = 0
    for k in range(len(predictions)):
        if predictions[k] == actual_outputs[k]:
            correct_cases += 1
        else:
            incorrect_cases += 1
    total = correct_cases + incorrect_cases
    perc_correct = (correct_cases / total) * 100
    perc_incorrect = (incorrect_cases / total) * 100
    return perc_correct

#train and return all trees
def train_trees(number_of_trees, attributes, training_data_input, training_data_output):
    trees = []
    # Parent call to recursive function
    for i in range(1, number_of_trees + 1):
        # the binary target for index i
        y_tree = list(map(lambda value: value == i if 1 else 0, training_data_output))
        trees.append(decision_tree_learning(training_data_input, attributes, y_tree))
    return trees

#get accuracy of each tree depending on results of each
def get_tree_priority(trees, validation_data_input, validation_data_output):
    number_of_trees = len(trees)
    tree_priority = [0] * number_of_trees
    for t in range(number_of_trees):
        tree = trees[t]
        tree_priority[t] = get_perc_accuracy(tree, t + 1, validation_data_input, validation_data_output)
    return tree_priority

#get percentage accuracy of the tree
def get_perc_accuracy(tree, emotion_val, x, y):
    correct = 0
    for i in range(len(x)):
        output, _, _ = tree.parse_tree(x[i], 0)
        if (y[i] == emotion_val and output) or (y[i] != emotion_val and (not output)):
            correct += 1
    return correct / len(x)

#get final predictions given trees and test_data
def get_predictions(trees, test_data, tree_priority, randomise):
    number_of_trees = len(trees)
    final_result = [0] * len(test_data)
    for i in range(len(test_data)):
        test_case_output = [(0,0,0)] * number_of_trees
        for t in range(number_of_trees):
            output, entropy, height = trees[t].parse_tree(test_data[i], 0)
            test_case_output[t] = (output, entropy, height)
        if randomise:
            final_result[i] = get_emotion_val_rand(test_case_output)
        else:
            final_result[i] = get_emotion_val(test_case_output, tree_priority)
    return final_result

#get final output using random strategy
def get_emotion_val_rand(output):
    trues = []
    for i in range(len(output)):
        if output[i]:
            trues.append(i)
    if len(trues) == 0:
        return random.randint(1, len(output))
    return random.choice(trues) + 1

#get final output depending on final output and tree_priority
def get_emotion_val(output, tree_priority):
    heights = []
    all_false = True
    for i in range(len(output)):
        # If tree's output is positive (identifies emotion positively)
        if output[i][0]:
            all_false = False
            heights.append(output[i][2])
        else:
            heights.append(-output[i][2] + sys.maxsize)
    min_height = min(heights)
    counter = collections.Counter(heights)
    if counter[min_height] > 1:
        # Incase multiple emotion values with same height value
        entropy_priorities = []
        for i in range(len(output)):
            if heights[i] == min_height:
                entropy_priorities.append(output[i][1])
            else:
                entropy_priorities.append(1 - output[i][1])
        return entropy_priorities.index(min(entropy_priorities)) + 1
    else:
        return heights.index(min_height) + 1

def decision_tree_learning(examples, attributes, binary_targets):
    if same_binary_targets(binary_targets):
        return TreeNode.create_leaf(binary_targets[0], 0)
    elif len(attributes) == 0:
        counter = collections.Counter(binary_targets)
        return TreeNode.create_leaf(majority_value(binary_targets), get_entropy(counter[1], counter[0]))
    else:
        best_attribute = choose_best_decision_attribute(examples, attributes, binary_targets)
        tree = TreeNode.create_internal(best_attribute)
        for v in [0, 1]:
            v_examples = []
            v_binary_targets = []
            for i in range(0, len(examples)):
                example = examples[i]
                if example[best_attribute - 1] == v:
                    v_examples.append(example)
                    v_binary_targets.append(binary_targets[i])

            if len(v_examples) == 0:
                counter = collections.Counter(binary_targets)

                return TreeNode.create_leaf(majority_value(binary_targets), get_entropy(counter[1], counter[0]))
            else:
                attributes.remove(best_attribute)
                subtree = decision_tree_learning(v_examples, attributes, v_binary_targets)
                tree.add_kid(subtree)
                attributes.append(best_attribute)
        return tree

# checks if binary_targets vector contains same values
def same_binary_targets(binary_targets):
    if len(binary_targets) <= 0:
        return True
    first_target = binary_targets[0]
    for target in binary_targets:
        if target != first_target:
            return False
    return True

# finds the mode of the vector
def majority_value(binary_targets):
    return max(set(binary_targets), key=binary_targets.count)


def get_entropy(p, n):
    if p == 0 or n == 0:
        return 0
    return -(p/(p+n)) * math.log(p/(p+n), 2) - (n/(p+n)) * math.log(n/(p+n), 2)


# find between 1 and 45
def choose_best_decision_attribute(examples, attributes, binary_targets):
    max_gain = -1
    maxs = []

    for index, attr in enumerate(attributes):
        p0 = 0
        n0 = 0
        p1 = 0
        n1 = 0
        p = 0
        n = 0

        for i in range(0, len(examples)):
            example = examples[i]
            if example[attr - 1] == 0:
                if binary_targets[i] == 1:
                    p0 += 1
                    p += 1
                else:
                    n0 += 1
                    n += 1
            else:
                if binary_targets[i] == 1:
                    p1 += 1
                    p += 1
                else:
                    n1 += 1
                    n += 1

        remainder = ((p0 + n0) / (p + n)) * get_entropy(p0, n0) + \
                    ((p1 + n1) / (p + n)) * get_entropy(p1, n1)
        gain = get_entropy(p, n) - remainder
        if gain > max_gain:
            max_gain = gain
            maxs = [index]
        elif gain == max_gain:
            maxs.append(index)

    if len(maxs) == 0:
        raise ValueError("Index is -1")

    return attributes[random.choice(maxs)]


def dump_tree(tree_name, tree):
    print("-------------------------------------------------------------------")
    print("Tree Name: " + str(tree_name))
    print(tree.to_string())
    print("-------------------------------------------------------------------")


def test_debug():
    # 1
    # |-2
    # |-3
    # | |-4
    # |   |-5
    # |-6
    tree_test_case = \
        TreeNode.create_internal("1").add_kid(TreeNode.create_leaf("2")) \
            .add_kid(TreeNode.create_internal("3").add_kid(TreeNode.create_internal("4").add_kid(TreeNode.create_leaf("5")))) \
            .add_kid(TreeNode.create_leaf("6"))
    dump_tree("Test", tree_test_case)


if __name__ == "__main__":
    main()
    # test_debug()
