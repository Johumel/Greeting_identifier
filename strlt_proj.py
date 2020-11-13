#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 11 22:06:57 2020

@author: john.onwuemeka
"""

import streamlit as st
import numpy as np
import csv
import h5py
import mpu
from keras.models import Model,load_model
from keras.layers import Dense, Input, Dropout, LSTM, Activation
from keras.layers.embeddings import Embedding
from keras.preprocessing import sequence
from keras.initializers import glorot_uniform



def read_glove_vecs(glove_file):
    with open(glove_file, 'r') as f:
        words = set()
        word_to_vec_map = {}
        for line in f:
            line = line.strip().split()
            curr_word = line[0]
            words.add(curr_word)
            word_to_vec_map[curr_word] = np.array(line[1:], dtype=np.float64)
        
        i = 1
        words_to_index = {}
        index_to_words = {}
        for w in sorted(words):
            words_to_index[w] = i
            index_to_words[i] = w
            i = i + 1
    return words_to_index, index_to_words, word_to_vec_map


def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def read_csv(fname):
    text = []
    classy = []

    with open (fname) as csvDataFile:
        csvReader = csv.reader(csvDataFile)

        for row in csvReader:
            text.append(row[6])
            classy.append(row[7])

    X = np.asarray(text)
    Y = np.asarray(classy, dtype=int)

    return X, Y


def cleanX(X):
    for h in range(len(X)):
        i = X[h]
        nh = i.split()
        new_nh = []
        for j in nh:
            j = j.strip("..,)(:?$#@&!;")
            if "'" in j:
                j = j.replace("'","")
            if '.' in j:
                j = j.split('.')
            elif '/' in j:
                j = j.split('/')
            elif '-' in j:
                j = j.split('-')
            elif j == 'speedbird':
                j = [j[0:5],j[5:]]
            if isinstance(j,list):
                new_nh.append(j[0])
                new_nh.append(j[1])
            else:
                new_nh.append(j)
        X[h] = ' '.join(new_nh)
    return X

              
def label_to_type(label):
    if label >= 0.5:
        return 'contains a Greeting'
    else:
        return 'does not contain a Greeting'
        

def predict(X, Y, W, b, word_to_vec_map):
    """
    Given X (sentences) and Y (emoji indices), predict emojis and compute the accuracy of your model over the given set.
    
    Arguments:
    X -- input data containing sentences, numpy array of shape (m, None)
    Y -- labels, containing index of the label emoji, numpy array of shape (m, 1)
    
    Returns:
    pred -- numpy array of shape (m, 1) with your predictions
    """
    m = X.shape[0]
    pred = np.zeros((m, 1))
    
    for j in range(m):                       # Loop over training examples
        
        # Split jth test example (sentence) into list of lower case words
        words = X[j].lower().split()
        
        # Average words' vectors
        avg = np.zeros((50,))
        for w in words:
            try:
                fd = word_to_vec_map[w]
            except:
                fd = word_to_vec_map['unknown']
            avg += fd
        avg = avg/len(words)

        # Forward propagation
        Z = np.dot(W, avg) + b
        A = sigmoid(Z)
        pred[j] = A
        
    predictions = np.asarray([1 if i[0] >=0.5 else 0 for i in pred])
    accur = np.mean(predictions[:] == Y[:])
    
    return pred,accur

def sentence_to_avg(sentence, word_to_vec_map,i):
    """
    Converts a sentence (string) into a list of words (strings). Extracts the GloVe representation of each word
    and averages its value into a single vector encoding the meaning of the sentence.
    
    Arguments:
    sentence -- string, one training example from X
    word_to_vec_map -- dictionary mapping every word in a vocabulary into its 50-dimensional vector representation
    
    Returns:
    avg -- average vector encoding information about the sentence, numpy-array of shape (50,)
    """
    
    #split the words in the sentence
    words = [i.lower() for i in sentence.split()]
    
    #set the embeddings of unknown words prior to initialization
    try:
        fd = word_to_vec_map[words[0]]
    except:
        fd = word_to_vec_map['unknown']
        
    # Initialize the average word vector, should have the same shape as your word vectors.
    avg = np.zeros(fd.shape) 

    # average the word vectors..
    total = np.zeros(avg.shape).tolist()
    for w in words:
        #set the embeddings of unknown words
        try:
            fd = word_to_vec_map[w]
        except:
            fd = word_to_vec_map['unknown']
        total += fd
    avg = np.asarray(total/len(words))
    
    return avg

#Build the predictor model
# @st.cache()
def model_we(X, Y, word_to_vec_map, learning_rate = 0.01, num_iterations = 400):
     """
    Model to train word vector representations in numpy.
    
    Arguments:
    X -- input data, numpy array of sentences as strings, of shape (m, 1)
    Y -- labels, numpy array of integers between 0 and 7, numpy-array of shape (m, 1)
    word_to_vec_map -- dictionary mapping every word in a vocabulary into its 50-dimensional vector representation
    learning_rate -- learning_rate for the stochastic gradient descent algorithm
    num_iterations -- number of iterations
    
    Returns:
    pred -- vector of predictions, numpy-array of shape (m, 1)
    W -- weight matrix of the softmax layer, of shape (n_y, n_h)
    b -- bias of the softmax layer, of shape (n_y,)
    """
    
    np.random.seed(1)

    # Define number of training examples
    m = Y.shape[0]                          # number of training examples
    n_y = 1                                 # number of classes  
    n_h = 50                                # dimensions of the GloVe vectors 
    
    # Initialize parameters using Xavier initialization
    W = np.random.randn(n_y, n_h) / np.sqrt(n_h)
    b = np.zeros((n_y,))

    
    # Optimization loop
    for t in range(num_iterations): # Loop over the number of iterations
        cost = 0
        for i in range(m):          # Loop over the training examples
            
            # Average the word vectors of the words from the i'th training example
            avg = sentence_to_avg(X[i], word_to_vec_map)

            # Forward propagate the avg through the softmax layer
            z = np.dot(W,avg)+b
            a = sigmoid(z)

            # Compute cost
            cost += -1*(Y[i]*np.log(a)[0] -(1-Y[i])*np.log(1-a))
            
            # Compute gradients 
            dz = a - Y[i]
            dW = np.dot(dz.reshape(n_y,1), avg.reshape(1, n_h))
            db = dz

            # Update parameters with Stochastic Gradient Descent
            W = W - learning_rate * dW
            b = b - learning_rate * db
        
        if t % 100 == 0:
            print("Epoch: " + str(t) + " --- cost = " + str((cost/m)[0]))
            pred,_ = predict(X, Y, W, b, word_to_vec_map) #predict is defined in emo_utils.py

    return pred, W, b

def pel(word_to_vec_map, word_to_index):
    """
    Creates a Keras Embedding() layer and loads in pre-trained GloVe 50-dimensional vectors.
    
    Arguments:
    word_to_vec_map -- dictionary mapping words to their GloVe vector representation.
    word_to_index -- dictionary mapping from words to their indices in the vocabulary (400,001 words)

    Returns:
    embedding_layer -- pretrained layer Keras instance
    """
    
    vocab_len = len(word_to_index) + 1                  # adding 1 to fit Keras embedding (requirement)
    emb_dim = word_to_vec_map["cucumber"].shape[0]      # define dimensionality of your GloVe word vectors (= 50)
    
    # Initialize the embedding matrix as a numpy array of zeros.
    emb_matrix = np.zeros((vocab_len,emb_dim))
    
    # Set each row "idx" of the embedding matrix to be 
    # the word vector representation of the idx'th word of the vocabulary
    for word, idx in word_to_index.items():
        #set the embeddings of unknown words
        try:
            fd = word_to_vec_map[word]
        except:
            fd = word_to_vec_map['unknown']
        emb_matrix[idx, :] = fd

    # Define Keras embedding layer with the correct input and output sizes
    embedding_layer = Embedding(input_dim=vocab_len,output_dim=emb_dim,trainable = False)

    # Build the embedding layer, it is required before setting the weights of the embedding layer. 
    embedding_layer.build((None,))
    
    # Set the weights of the embedding layer to the embedding matrix.
    embedding_layer.set_weights([emb_matrix])
    
    return embedding_layer

def s_2_i(X, word_to_index, max_len):
    """
    Converts an array of sentences (strings) into an array of indices corresponding to words in the sentences.
    The output shape should be such that it can be given to `Embedding()` (described in Figure 4). 
    
    Arguments:
    X -- array of sentences (strings), of shape (m, 1)
    word_to_index -- a dictionary containing the each word mapped to its index
    max_len -- maximum number of words in a sentence. You can assume every sentence in X is no longer than this. 
    
    Returns:
    X_indices -- array of indices corresponding to words in the sentences from X, of shape (m, max_len)
    """
    
    m = X.shape[0]                                   # number of training examples
    
    # Initialize X_indices as a numpy matrix of zeros and the correct shape (≈ 1 line)
    X_indices = np.zeros((m,max_len))
    
    for i in range(m):                               # loop over training examples
        
        # Convert the ith training sentence in lower case and split is into words. You should get a list of words.
        sentence_words = [k.lower() for k in X[i].split()]
        
        # Initialize j to 0
        j = 0
        
        # Loop over the words of sentence_words
        for w in sentence_words:
            if j< max_len:
                # Set the (i,j)th entry of X_indices to the index of the correct word.
                try:
                    fd = word_to_index[w]
                except:
                    fd = word_to_index['unknown']
                X_indices[i, j] = fd
                j += 1
                
    return X_indices

# @st.cache()
def model_lstm(X,train,Y_train,maxLen, word_to_vec_map, word_to_index):
    """
    Function creating the Emojify-v2 model's graph.
    
    Arguments:
    input_shape -- shape of the input, usually (max_len,)
    word_to_vec_map -- dictionary mapping every word in a vocabulary into its 50-dimensional vector representation
    word_to_index -- dictionary mapping from words to their indices in the vocabulary (400,001 words)

    Returns:
    model -- a model instance in Keras
    """
    

    # Define sentence_indices as the input of the graph.
    input_shape = (maxLen,)
    sentence_indices = Input(shape=input_shape, dtype='int32')
    
    # Create the embedding layer pretrained with GloVe Vectors
    embedding_layer = pel(word_to_vec_map, word_to_index)
    
    # Propagate sentence_indices through your embedding layer
    # (See additional hints in the instructions).
    embeddings =  embedding_layer(sentence_indices)
    
    # Propagate the embeddings through an LSTM layer with 128-dimensional hidden state
    X = LSTM(units = 128, return_sequences=True)(embeddings)
    
    # Add dropout with a probability of 0.5
    X = Dropout(rate = 0.7 )(X)
    
    # Propagate X trough another LSTM layer with 128-dimensional hidden state
    X = LSTM(units = 128, return_sequences=False)(X)
    
    # Add dropout with a probability of 0.5
    X = Dropout(rate = 0.7 )(X)
    
    # Propagate X through a Dense layer with 2 units
    X = Dense(1)(X)
    
    # Add a softmax activation
    X = Activation(activation='sigmoid')(X)
    
    # Create Model instance which converts sentence_indices into X.
    model = Model(inputs=sentence_indices, outputs=X)
    
    #compile model
    model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
        
    #prepare model input
    X_train_indices = s_2_i(X_train, word_to_index, maxLen)
    Y_train_oh = np.asarray([[i] for i in Y_train])
        
    #train the model for 50 epochs with minibatching
    model.fit(X_train_indices, Y_train_oh, epochs = 20, batch_size = 32, shuffle=True)
        
    return model

def load_variables(fname):
    x = mpu.io.read(fname)
    return x

def main():
    st.title("Identify the presence of Greetings")
    
    #load data set
    fname = './tagged_selections_by_sentence.csv'
    X_,Y_ = read_csv(fname)
    
    #clean-up dataset
    X_ = cleanX(X_)
    
    #split data set into training and test sets    
    ll = int(np.ceil(len(X_)*0.8))
    X_train,Y_train = X_[0:ll],Y_[0:ll]
    X_test,Y_test = X_[ll:],Y_[ll:]
    
    #set maxlen as the length of the longest sentence
    #set to 10 because a greeting would most likely be
    #within the first few sentences
    maxLen = 10 #len(max(X_train, key=len).split())
    
    
    #load word embeddings
    #word embeddings download from https://github.com/uclnlp/inferbeddings/blob/master/data/glove/
    w1 = load_variables('./word_to_vec_map_1.pickle')
    w2 = load_variables('./word_to_vec_map_2.pickle')
    word_to_vec_map = w1.copy()
    word_to_vec_map.update(w2)
    word_to_index = load_variables('./word_to_index.pickle')
    index_to_word = load_variables('./index_to_word.pickle')
    
    build_model = st.checkbox("Check to build model otherwise pretrained model will be loaded")
    if(build_model):
            
        choose_model = st.sidebar.selectbox("Choose the NLP model",
        		[ "WE", "LSTM"])
        
        if (choose_model == "WE"):
            
            #train your model
            st.text("Building WE model .... ")
            pred, W, b = model(X_train, Y_train, word_to_vec_map)
            st.text("Done building WE model ")
            
            #evaluate model performance
            st.text("Evaluating model performance .... ")
            pred_train,accur_train = predict(X_train, Y_train, W, b, word_to_vec_map)
            pred_test,accur_test = predict(X_test, Y_test, W, b, word_to_vec_map)
            st.text("Accuracy of training set is: ")
            st.write('%.1f' % accur_train)
            st.text("Accuracy of test set is: ")
            st.write('%.1f' % accur_test)
            st.text("Done evaluating model performance")
    
            #request user input
            user_data = st.text_input("Enter sentence here: ")	
            
            #clean up input
            user_data = cleanX(np.array([user_data]))
            
            #make prediction
            pred,_ = predict(user_data, np.array([1]), W, b, word_to_vec_map)
            out = label_to_type(pred[0])
            st.write('Your sentence ', out.lower())
        
        elif (choose_model == "LSTM"):
            st.text("Building lstm model .... ")
            model = model_lstm(X_train,Y_train,maxLen, word_to_vec_map, word_to_index)
            st.text("Done building lstm model ")
            
            #evaluate model on test set
            X_test_indices = s_2_i(X_test, word_to_index, maxLen)
            Y_test_oh = np.asarray([[i] for i in Y_test])
            
            st.text("Evaluating model performance .... ")
            loss, acc = model.evaluate(X_test_indices, Y_test_oh)
            st.text("Accuracy of test set is: ")
            st.write(round(acc,2))
            st.text("Done evaluating model performance")
    
            #request user input
            user_data = st.text_input("Enter sentence here: ")	
            X_indices = s_2_i(cleanX(np.array([user_data])), word_to_index, maxLen)
            pred = model.predict(X_indices)
            out = label_to_type(pred[0])
            st.write('Your sentence ', out.lower()) # Inverse transform to get the original dependent value. 
    
    else:
        choose_model = st.sidebar.selectbox("Choose the NLP model",
        		[ "WE", "LSTM"])
        
        if (choose_model == "WE"):
            
            #load pretrained weights
            filename = './trained_weights_we.h5'
            ft = h5py.File(filename,'r')
            W = ft['W']
            b = ft['b']
            ft.close()
            
            #request user input
            user_data=[]
            user_data = st.text_input("Enter sentence here: ")
            if(user_data):
                
                #clean up input
                user_data = cleanX(np.array([user_data]))
                
                #make prediction
                pred,_ = predict(user_data, np.array([1]), W, b, word_to_vec_map)
                out = label_to_type(pred[0])
                st.write('Probability is ',str(pred[0]))
                st.write('Your sentence ', out.lower())
                
        elif(choose_model == "LSTM"):
            
            # load model
            fname = './trained_model_lstm.h5'
            model = load_model(fname)
            
            #request user input
            user_data=[]
            user_data = st.text_input("Enter sentence here: ")
            if (user_data):
    
                #request user input
                user_data = st.text_input("Enter sentence here: ")	
                X_indices = s_2_i(cleanX(np.array([user_data])), word_to_index, maxLen)
                pred = model.predict(X_indices)
                out = label_to_type(pred[0])
                st.write('Your sentence ', out.lower()) 
    
if __name__ == "__main__":
    main()