import operator
import os
import pickle
import sys
import warnings

import numpy as np
import pandas
from sklearn import neighbors, svm, tree
from sklearn.ensemble import RandomForestClassifier
from sklearn.externals.six import StringIO
from sklearn.metrics import precision_recall_fscore_support
from sklearn.naive_bayes import GaussianNB
import pydotplus

sys.path.append('../Utilities/')
sys.path.append('../../Data Transformation/integrated')
sys.path.append('../../hyperopt-sklearn')
from get_conventions import get_problem_model_file_convention, get_problem_dataset_file_convention, \
    get_problem_metrics_file_convention
from constants import performance_metric_keys, ClassifierType, PlatformType, Metrics, defaultTestSize
from hpsklearn import HyperoptEstimator, any_classifier, knn, svc, random_forest
from hyperopt import tpe
from get_probs import get_all_probs_without_category_NA
from generate_problems_dataset import generateLazyLoad
import transform_description


# with open('test_size.pickle') as f:
#     test_size = pickle.load(f)

def calculateExpectedValue(valuesAsNumpyArray):
    return np.mean(valuesAsNumpyArray)


def calculateBias(fX, fCapX):
    errors = np.array([])
    for i in range(len(fX)):
        errors = np.append(errors, abs(fCapX[i] - fX[i]))
    return calculateExpectedValue(errors)


def calculateVariance(fX, fCapX):
    squaredFCaps = fCapX ** 2
    return calculateExpectedValue(squaredFCaps) - (calculateExpectedValue(fCapX) ** 2)


def calculateTotalError(fX, fCapX):
    errors = np.array([])
    for i in range(len(fX)):
        errors = np.append(errors, (fCapX[i] - fX[i]) ** 2)
    return np.mean(errors)


def calculateIrreducibleError(fX, fCapX):
    return calculateTotalError(fX, fCapX) - (calculateBias(fX, fCapX) ** 2) - calculateVariance(fX, fCapX)


def train_for_categoryModel1(platform, number_of_top_words, category, classifier, test_size=defaultTestSize):

    modelFileConvention = get_problem_model_file_convention(platform = platform, model_number = 1,
                                                            category_or_problemWise = "catWise",
                                                            number_of_top_words = number_of_top_words,
                                                            category = category, test_size = test_size,
                                                            classifier = classifier)
    dataFileConvention = get_problem_dataset_file_convention(platform = platform, model_number = 1,
                                                             number_of_top_words = number_of_top_words,
                                                             category = category, test_size = test_size)

    df = pandas.read_csv('data/' + category + '/' + dataFileConvention + '_dataset.csv')
    X = np.array(df.drop(['class', 'sub_size', 'time_limit'], 1)).astype(float)
    y = np.array(df['class']).astype(int)

    X_train = X[:-int(len(X) * test_size)]
    y_train = y[:-int(len(y) * test_size)]
    X_test = X[-int(len(X) * test_size):]
    y_test = y[-int(len(y) * test_size):]

    clf = None
    if classifier == ClassifierType.KNN:
        clf = neighbors.KNeighborsClassifier()
    elif classifier == ClassifierType.SVM:
        clf = svm.SVC(probability = True)
    elif classifier == ClassifierType.DECISIONTREE:
        clf = tree.DecisionTreeClassifier()
    elif classifier == ClassifierType.RANDOMFOREST:
        clf = RandomForestClassifier()
    elif classifier == ClassifierType.NAIVEBAYES:
        clf = GaussianNB()
    elif classifier == ClassifierType.HPKNN:
        clf = HyperoptEstimator(classifier = knn('clf'))
    elif classifier == ClassifierType.HPSVM:
        clf = HyperoptEstimator(classifier = svc('clf', max_iter = 20000000))
    elif classifier == ClassifierType.HPRANDOMFOREST:
        clf = HyperoptEstimator(classifier = random_forest('clf'))
    elif classifier == ClassifierType.HYPERSKLEARN:
        clf = HyperoptEstimator(classifier = any_classifier('clf'), algo = tpe.suggest, trial_timeout = 60)
    else:
        print "Enter valid classifier"

    warnings.filterwarnings("error")
    try:
        clf.fit(X_train, y_train)
        accuracy = clf.score(X_test, y_test)
        if classifier == ClassifierType.DECISIONTREE:
            dot_data = StringIO()
            tree.export_graphviz(clf, out_file = dot_data)
            graph = pydotplus.graph_from_dot_data(dot_data.getvalue())
            graph.write_pdf('dt' + category + '.pdf')
            print('pdf written')

    except Exception as e:
        print('got training error')
        print(str(e))
        m = Metrics(category = category)
        m.isValid = False
        m.invalidityMessage = 'Training Failed'
        return m
    warnings.filterwarnings("always")
    print("Classifier trained")

    if classifier == ClassifierType.HYPERSKLEARN:
        print('Best model is ' + str(clf.best_model()))
    print "accuracy : " + str(accuracy)

    fCapX = np.array([])
    fX = np.array([])
    y_predictions = []
    print("Predictions started")

    if classifier == ClassifierType.HYPERSKLEARN or classifier in ClassifierType.onlyHyperClassifiers:
        y_predictions = clf.predict(X_test)
        print(type(y_predictions))
        print(str(y_predictions.shape))
        for i in range(len(X_test)):
            fCapX = np.append(fCapX, y_predictions[i])
            fX = np.append(fX, y_test[i])
    else:
        for i in range(len(X_test)):
            current_prediction = clf.predict_proba(X_test[i].reshape(1, -1))
            y_predictions.append(0 if current_prediction[0][0] > 0.5 else 1)
            fCapX = np.append(fCapX, current_prediction[0][1])
            fX = np.append(fX, y_test[i])

    bias = calculateBias(fX, fCapX)
    variance = calculateVariance(fX, fCapX)
    totalError = calculateTotalError(fX, fCapX)
    irreducibleError = calculateIrreducibleError(fX, fCapX)

    print("Bias Variance Calculated")
    print('Total Error: ' + str(totalError))
    print('Bias: ' + str(bias))
    print('Variance: ' + str(variance))
    print('Irreducible Error: ' + str(irreducibleError))

    count_metrics = {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0}
    for i in range(len(y_test)):
        if y_predictions[i] == 1:
            if y_test[i] == 1:
                count_metrics['tp'] += 1
            else:
                count_metrics['fp'] += 1
        else:
            if y_test[i] == 1:
                count_metrics['fn'] += 1
            else:
                count_metrics['tn'] += 1

    warnings.filterwarnings("error")
    try:
        performance_metrics = precision_recall_fscore_support(np.array(y_test), np.array(y_predictions))
    except Exception as e:
        print(str(e))
        print('performance metrics not valid')
        m = Metrics(category = category)
        m.isValid = False
        m.invalidityMessage = 'Performance metrics invalid'
        return m
    warnings.filterwarnings("always")

    with open('model/' + modelFileConvention + '.pickle', 'w') as f:
        print('Dumping model: ' + 'model/' + modelFileConvention + '.pickle')
        pickle.dump(clf, f)

    print "precision : " + str(performance_metrics[performance_metric_keys['precision']])
    print "recall : " + str(performance_metrics[performance_metric_keys['recall']])
    print "fscore : " + str(performance_metrics[performance_metric_keys['fscore']])

    return Metrics(category = category, truePositive = count_metrics['tp'], trueNegative = count_metrics['tn'],
                   falsePositive = count_metrics['fp'], falseNegative = count_metrics['fn'],
                   precision = performance_metrics[performance_metric_keys['precision']],
                   recall = performance_metrics[performance_metric_keys['recall']],
                   fScore = performance_metrics[performance_metric_keys['fscore']],
                   bias = bias, variance = variance, irreducibleError = irreducibleError, totalError = totalError)


def train_for_categoryModel2(category, classifier, uniqueFileConvention, dataFileConvention, test_size=defaultTestSize):
    modelFileConvention = uniqueFileConvention + '_' + category + '_' + str(test_size) \
                          + '_' + ClassifierType.classifierTypeString[classifier]
    df = pandas.read_csv('data/' + category + '/' + dataFileConvention + '_dataset.csv')
    df1 = df.ix[:, :-1]
    df2 = df.ix[:, -1:]

    # print 'DataFrame Shape: '+str(df1.shape)
    # print 'DataFrame2 Shape: '+str(df2.shape)

    X = np.array(df1)
    y = np.array(df2)
    X_train = X[:-int(len(X) * test_size)]
    y_train = y[:-int(len(y) * test_size)]

    X_test = X[-int(len(X) * test_size):]
    y_test = y[-int(len(y) * test_size):]

    if classifier == ClassifierType.KNN:
        clf = neighbors.KNeighborsClassifier()
    elif classifier == ClassifierType.SVM:
        clf = svm.SVC(probability = True)
    elif classifier == ClassifierType.DECISIONTREE:
        clf = tree.DecisionTreeClassifier()
    elif classifier == ClassifierType.RANDOMFOREST:
        clf = RandomForestClassifier()
    elif classifier == ClassifierType.NAIVEBAYES:
        clf = GaussianNB()
    elif classifier == ClassifierType.HPKNN:
        clf = HyperoptEstimator(classifier = knn('clf'))
    elif classifier == ClassifierType.HPSVM:
        clf = HyperoptEstimator(classifier = svc('clf', max_iter = 20000000))
    elif classifier == ClassifierType.HPRANDOMFOREST:
        clf = HyperoptEstimator(classifier = random_forest('clf'))
    elif classifier == ClassifierType.HYPERSKLEARN:
        clf = HyperoptEstimator(classifier = any_classifier('clf'), algo = tpe.suggest, trial_timeout = 60)
    else:
        clf = None
        print "Enter valid classifier"

    warnings.filterwarnings("error")
    try:
        print('Classifier Training started')
        clf.fit(X_train, y_train.ravel())
        accuracy = clf.score(X_test, y_test.ravel())
    except Exception as e:
        print('got training error')
        print e
        m = Metrics(category = category)
        m.isValid = False
        m.invalidityMessage = 'Training Failed'
        return m
    warnings.filterwarnings("always")

    print("Classifier trained")

    if classifier == ClassifierType.HYPERSKLEARN:
        print('Best model is ' + str(clf.best_model()))
    print "accuracy : " + str(accuracy)

    fCapX = np.array([])
    fX = np.array([])
    y_predictions = []
    print("Predictions started")

    if classifier == ClassifierType.HYPERSKLEARN or classifier in ClassifierType.onlyHyperClassifiers:
        y_predictions = clf.predict(X_test)
        print(type(y_predictions))
        print(str(y_predictions.shape))
        for i in range(len(X_test)):
            fCapX = np.append(fCapX, y_predictions[i])
            fX = np.append(fX, y_test[i])
    else:
        for i in range(len(X_test)):
            current_prediction = clf.predict_proba(X_test[i].reshape(1, -1))
            y_predictions.append(0 if current_prediction[0][0] > 0.5 else 1)
            fCapX = np.append(fCapX, current_prediction[0][1])
            fX = np.append(fX, y_test[i])

    bias = calculateBias(fX, fCapX)
    variance = calculateVariance(fX, fCapX)
    totalError = calculateTotalError(fX, fCapX)
    irreducibleError = calculateIrreducibleError(fX, fCapX)

    print("Bias Variance Calculated")
    print('Total Error: ' + str(totalError))
    print('Bias: ' + str(bias))
    print('Variance: ' + str(variance))
    print('Irreducible Error: ' + str(irreducibleError))

    count_metrics = {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0}
    for i in range(len(y_test)):
        if y_predictions[i] == 1:
            if y_test[i] == 1:
                count_metrics['tp'] += 1
            else:
                count_metrics['fp'] += 1
        else:
            if y_test[i] == 1:
                count_metrics['fn'] += 1
            else:
                count_metrics['tn'] += 1

    warnings.filterwarnings("error")
    try:
        performance_metrics = precision_recall_fscore_support(np.array(y_test), np.array(y_predictions))
    except:
        print('performance metrics not valid')
        m = Metrics(category = category)
        m.isValid = False
        m.invalidityMessage = 'Performance metrics invalid'
        return m
    warnings.filterwarnings("always")

    print "precision : " + str(performance_metrics[performance_metric_keys['precision']])
    print "recall : " + str(performance_metrics[performance_metric_keys['recall']])
    print "fscore : " + str(performance_metrics[performance_metric_keys['fscore']])

    if not os.path.exists('model'):
        os.makedirs('model')
    with open('model/' + modelFileConvention + '.pickle', 'w') as f:
        print('Dumping model: ' + 'model/' + modelFileConvention + '.pickle')
        pickle.dump(clf, f)

    return Metrics(category = category, truePositive = count_metrics['tp'], trueNegative = count_metrics['tn'],
                   falsePositive = count_metrics['fp'], falseNegative = count_metrics['fn'],
                   precision = performance_metrics[performance_metric_keys['precision']],
                   recall = performance_metrics[performance_metric_keys['recall']],
                   fScore = performance_metrics[performance_metric_keys['fscore']],
                   bias = bias, variance = variance, irreducibleError = irreducibleError, totalError = totalError)


# Deprecated method for model 2
def get_accuracy(categories, classifier, useIntegrated=True, platform=PlatformType.Default, modelNumber=1, test_size=defaultTestSize, number_of_top_words=10):
    preds_for_prob = {}
    ans_for_prob = {}

    for category in categories:
        print('Processing for category: ' + category)

        modelFileConvention = get_problem_model_file_convention(platform = platform, model_number = modelNumber,
                                                                category_or_problemWise = "catWise",
                                                                number_of_top_words = number_of_top_words,
                                                                category = category, test_size = test_size,
                                                                classifier = classifier)
        dataFileConvention = get_problem_dataset_file_convention(platform = platform, model_number = modelNumber,
                                                                 number_of_top_words = number_of_top_words,
                                                                 category = category, test_size = test_size)
        print('Generating dataset file')
        generateLazyLoad(useIntegrated = useIntegrated, category = category, platform = platform,
                         shouldShuffle = False, test_size = test_size, number_of_top_words = number_of_top_words)
        df = pandas.read_csv("data/" + category + "/" + dataFileConvention + "_dataset.csv")
        X = np.array(df.drop(['class', 'sub_size', 'time_limit'], 1)).astype(float)
        y = np.array(df['class']).astype(int)

        X_test = X[-int(len(X) * test_size):]
        y_test = y[-int(len(y) * test_size):]

        if not os.path.isfile('model/' + modelFileConvention + '.pickle'):
            print('Model does not exist: ' 'model/' + modelFileConvention + '.pickle')
            print('Training dataset for building model')
            metrics = train_for_categoryModel1(platform = platform, number_of_top_words = number_of_top_words,
                                               category = category, classifier = classifier, test_size = test_size)
            if not metrics.isValid:
                return -1.0
        with open('model/' + modelFileConvention + '.pickle') as f:
            clf = pickle.load(f)

        # y_predictions = []
        for i in range(len(X_test)):
            if i not in preds_for_prob.keys():
                preds_for_prob[i] = {}

            if i not in ans_for_prob.keys():
                ans_for_prob[i] = []

            current_prediction = clf.predict_proba(X_test[i].reshape(1, -1))
            # print str(current_prediction[0][0]) + " " + str(current_prediction[0][1]) + '\t' + str(y_test[i]
            # y_predictions.append(current_prediction[0][1])
            preds_for_prob[i][category] = float(
                current_prediction[0][1])  # class 1 confidence i.e confidence for category c

            if y_test[i] == 1:
                ans_for_prob[i].append(category)

        print('=================== CATEGORY OVER ===================')
    correct = 0
    for i in range(len(X_test)):
        sorted_category_perc = sorted(preds_for_prob[i].items(), key = operator.itemgetter(1))
        sorted_category_perc.reverse()  # desc

        for j in range(3):
            if sorted_category_perc[j][0] in ans_for_prob[i]:
                correct += 1
                # print (sorted_category_perc[j][0] + " => " + str(ans_for_prob[i]))
                break

    accuracy = str(correct * 1.0 / len(X_test))
    print('accuracy = ' + str(accuracy))
    return accuracy


def createFeaturesForProbByCategory(prob, category, dataFileName):
    description = transform_description.transform(prob.modified_description)
    # filePath = 'data/'+category+'/'
    features = []
    with open("data/" + category + "/" + dataFileName + "_dataset.csv") as f:
        featureWords = f.readline().split(',')[0: -3]
        for word in featureWords:
            if description.count(word) > 0:
                features.append(1)
            else:
                features.append(0)
    return features
