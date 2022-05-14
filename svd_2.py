# -*- coding: utf-8 -*-

import argparse
import sys
import logging
import tensorflow as tf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sklearn.metrics

import SVD_common as svdc

def trainModel(dataset_name):
    global args;
    # Generate random seed
    #myrand=np.random.randint(1, 99999 + 1)
    myrand=71926
    np.random.seed(myrand)
    tf.random.set_seed(myrand)
    logging.debug("Random seed is: %s",myrand)
    
    # Set the global value
    WORDS_SIZE=10000
    INPUT_SIZE=500
    NUM_CLASSES=2
    EPOCHS=10
    
    train=pd.read_pickle("pickle_file/"+dataset_name+"_train.pickle")
    validate=pd.read_pickle("pickle_file/"+dataset_name+"_validate.pickle")
    test=pd.read_pickle("pickle_file/"+dataset_name+"_test.pickle")
    
    for dataset in [train, validate, test]:
        for col in range(1,6):
            dataset.iloc[:,col] = dataset.iloc[:,col].map({False: 0, True: 1})
            
    x_all = train['functionSource']
    pd.value_counts(train.iloc[:,1])
    one = train[train.iloc[:,1]==1].index.values.astype(int)
    zero = train[train.iloc[:,1]==0].index.values.astype(int)

    # Tokenizer with word-level
    tokenizer = tf.keras.preprocessing.text.Tokenizer(char_level=False)
    tokenizer.fit_on_texts(list(x_all))
    del(x_all)
    logging.debug('Number of tokens: %s',len(tokenizer.word_counts))
    # Reducing to top N words
    tokenizer.num_words = WORDS_SIZE
    # Top 10 words
    sorted(tokenizer.word_counts.items(), key=lambda x:x[1], reverse=True)[0:10]
    ## Tokkenizing train data and create matrix
    list_tokenized_train = tokenizer.texts_to_sequences(train['functionSource'])
    x_train = tf.keras.preprocessing.sequence.pad_sequences(list_tokenized_train, 
                                      maxlen=INPUT_SIZE,
                                      padding='post')
    x_train = x_train.astype(np.int64)
    
    ## Tokkenizing test data and create matrix
    list_tokenized_test = tokenizer.texts_to_sequences(test['functionSource'])
    x_test = tf.keras.preprocessing.sequence.pad_sequences(list_tokenized_test, 
                                     maxlen=INPUT_SIZE,
                                     padding='post')
    x_test = x_test.astype(np.int64)
    
    ## Tokkenizing validate data and create matrix
    list_tokenized_validate = tokenizer.texts_to_sequences(validate['functionSource'])
    x_validate = tf.keras.preprocessing.sequence.pad_sequences(list_tokenized_validate, 
                                     maxlen=INPUT_SIZE,
                                     padding='post')
    x_validate = x_validate.astype(np.int64)
    
    # Example data
    logging.debug('Train', pd.value_counts(train.iloc[:,1]))
    logging.debug('\nTest', pd.value_counts(test.iloc[:,1]))
    logging.debug('\nValidate', pd.value_counts(validate.iloc[:,1]))
    
    y_train=[]
    y_test=[]
    y_validate=[]
    
    for col in range(1,6):
        y_train.append(tf.keras.utils.to_categorical(train.iloc[:,col], num_classes=NUM_CLASSES).astype(np.int64))
        y_test.append(tf.keras.utils.to_categorical(test.iloc[:,col], num_classes=NUM_CLASSES).astype(np.int64))
        y_validate.append(tf.keras.utils.to_categorical(validate.iloc[:,col], num_classes=NUM_CLASSES).astype(np.int64))
    
    # Example data
    pd.value_counts(y_test[0][:,1])
    
    # Create a random weights matrix
    
    random_weights = np.random.normal(size=(WORDS_SIZE, 13),scale=0.01)
    
    # Must use non-sequential model building to create branches in the output layer
    model = tf.keras.Sequential(name="CNN")
    model.add(tf.keras.layers.Embedding(input_dim = WORDS_SIZE,
                                        output_dim = 13,
                                        weights=[random_weights],
                                        input_length = INPUT_SIZE))
    #model.add(tf.keras.layers.GaussianNoise(stddev=0.01))
    model.add(tf.keras.layers.Convolution1D(filters=512, kernel_size=(9), padding='same', activation='relu'))
    model.add(tf.keras.layers.MaxPool1D(pool_size=5))
    model.add(tf.keras.layers.Dropout(0.5))
    model.add(tf.keras.layers.Flatten())
    model.add(tf.keras.layers.Dense(64, activation='relu'))
    model.add(tf.keras.layers.Dense(16, activation='relu'))
    model.add(tf.keras.layers.Dense(1, activation='sigmoid'))
    
    # Define custom optimizers
    adam = tf.keras.optimizers.Adam(lr=0.005, beta_1=0.9, beta_2=0.999, epsilon=1, decay=0.0, amsgrad=False)
    
    ## Compile model with metrics
    model.compile(optimizer=adam, loss='binary_crossentropy', metrics=['accuracy'])
    logging.debug("CNN model built: ")
    model.summary()
    
    ## Create TensorBoard callbacks
    
    callbackdir= 'cb'
    
    tbCallback = tf.keras.callbacks.TensorBoard(log_dir=callbackdir, 
                             histogram_freq=1,
                             embeddings_freq=1,
                             write_graph=True, 
                             write_images=True)
    
    tbCallback.set_model(model)
    mld = 'model/model-ALL-last.hdf5'
    
    ## Create best model callback
    mcp = tf.keras.callbacks.ModelCheckpoint(filepath=mld, 
                                             monitor="val_loss",
                                             save_best_only=True, 
                                             mode='auto', 
                                             save_freq='epoch', 
                                             verbose=1)
    
    ceiling = 1019471

    class_weights = {0: 1., 1: 5.}
    
    history = model.fit(x = x_train[[*one,*zero[0:ceiling]],:],
          y = train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(),
          validation_data = (x_validate, validate.iloc[:,1].to_numpy()),
          epochs = EPOCHS,
          batch_size = 128,
          verbose =2,
          class_weight= class_weights,
          callbacks=[mcp,tbCallback])
    
    
    #with open('history/History-ALL-40EP-CNN', 'wb') as file_pi:
    #    pickle.dump(history.history, file_pi)
    
    # Load model
    model = tf.keras.models.load_model("model/model-ALL-last.hdf5")
    
    results = model.evaluate(x_train[[*one,*zero[0:ceiling]],:], train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), verbose=0, batch_size=128, )
    for num in range(0,len(model.metrics_names)):
        logging.debug(model.metrics_names[num]+': '+str(results[num]))
    
    predicted = model.predict_classes(x_train[[*one,*zero[0:ceiling]],:])
    predicted_prob = model.predict(x_train[[*one,*zero[0:ceiling]],:])
    
    logging.debug('\nConfusion Matrix')
    #predicted = model.predict_classes(x_test)
    confusion = sklearn.metrics.confusion_matrix(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_pred=predicted)
    logging.debug(confusion)
    
    tn, fp, fn, tp = confusion.ravel()
    logging.debug('\nTP:',tp)
    logging.debug('FP:',fp)
    logging.debug('TN:',tn)
    logging.debug('FN:',fn)
    
    ## Performance measure
    logging.debug('\nAccuracy: '+ str(sklearn.metrics.accuracy_score(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_pred=predicted)))
    logging.debug('Precision: '+ str(sklearn.metrics.precision_score(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_pred=predicted)))
    logging.debug('Recall: '+ str(sklearn.metrics.recall_score(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_pred=predicted)))
    logging.debug('F-measure: '+ str(sklearn.metrics.f1_score(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_pred=predicted)))
    logging.debug('Precision-Recall AUC: '+ str(sklearn.metrics.average_precision_score(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_score=predicted_prob)))
    logging.debug('AUC: '+ str(sklearn.metrics.roc_auc_score(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_score=predicted_prob)))
    logging.debug('MCC: '+ str(sklearn.metrics.matthews_corrcoef(y_true=train.iloc[[*one,*zero[0:ceiling]],1].to_numpy(), y_pred=predicted)))
        
    
    ## Test data

    results = model.evaluate(x_test, test.iloc[:,1].to_numpy(), batch_size=128)
    for num in range(0,len(model.metrics_names)):
        logging.debug(model.metrics_names[num]+': '+str(results[num]))
    
    predicted = model.predict_classes(x_test)
    predicted_prob = model.predict(x_test)
    
    confusion = sklearn.metrics.confusion_matrix(y_true=test.iloc[:,1].to_numpy(), y_pred=predicted)
    logging.debug(confusion)
    tn, fp, fn, tp = confusion.ravel()
    logging.debug('\nTP:',tp)
    logging.debug('FP:',fp)
    logging.debug('TN:',tn)
    logging.debug('FN:',fn)
    
    ## Performance measure
    logging.debug('\nAccuracy: '+ str(sklearn.metrics.accuracy_score(y_true=test.iloc[:,1].to_numpy(), y_pred=predicted)))
    logging.debug('Precision: '+ str(sklearn.metrics.precision_score(y_true=test.iloc[:,1].to_numpy(), y_pred=predicted)))
    logging.debug('Recall: '+ str(sklearn.metrics.recall_score(y_true=test.iloc[:,1].to_numpy(), y_pred=predicted)))
    logging.debug('F-measure: '+ str(sklearn.metrics.f1_score(y_true=test.iloc[:,1].to_numpy(), y_pred=predicted)))
    logging.debug('Precision-Recall AUC: '+ str(sklearn.metrics.average_precision_score(y_true=test.iloc[:,1].to_numpy(), y_score=predicted_prob)))
    logging.debug('AUC: '+ str(sklearn.metrics.roc_auc_score(y_true=test.iloc[:,1].to_numpy(), y_score=predicted_prob)))
    logging.debug('MCC: '+ str(sklearn.metrics.matthews_corrcoef(y_true=test.iloc[:,1].to_numpy(), y_pred=predicted)))
    
    
    model.metrics_names
    epochs_range = range(len(history.history[model.metrics_names[1]]))

    fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(20,15))
    fig.suptitle('CNN with 40 Epochs, maxpool of 5, class weights of 1:5')
    
    axs[0,0].plot(epochs_range, history.history[model.metrics_names[0]], 'b', label='Loss', color='red')
    axs[0,0].plot(epochs_range, history.history[model.metrics_names[1]], 'b', label='Accuracy', color='green')
    axs[0,0].set_title('Training accuracy & loss - CWE-119')
    axs[0,0].legend()
    
    
    axs[0,1].plot(epochs_range, history.history['val_%s'%(model.metrics_names[0])], 'b', label='Loss', color='red')
    axs[0,1].plot(epochs_range, history.history['val_%s'%(model.metrics_names[1])], 'b', label='Accuracy', color='green')
    axs[0,1].set_title('Validation accuracy & loss - CWE-119')
    axs[0,1].legend()
    
    
    
def main(): 
    global logger
    dataset_name = "VDISC"
    logger = svdc.configureLogging('svd_2.log', "DEBUG", False)
    svdc.convert2Pickle(dataset_name)
    trainModel(dataset_name)

logger = None

if __name__=="__main__": 
    main() 