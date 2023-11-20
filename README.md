# CSCI1460_Computational_Linguistics

Computational_Linguistics_CSCI1460
This course provides an introduction to the field of Natural Language Processing (NLP). We will focus on a range of NLP tasks, including machine translation, question answering, text classification, as well as the underlying linguistic problems (syntax, semantics, morphology) that make building sytems to solve these tasks so challenging. This course will cover both "traditional" (machine learning, information theoretic) approaches as well as "new" deep learning approaches.

There are 5 assignments and 1 final project:

1. You will be implementing BOW for sentiment classification. In this assignment, you will be using a very useful NLP library (spaCy), and a popular machine learning library (scikit-learn, or sklearn) to help you with implementing a standard ML workflow.

2. In this project you will leverage skills that you have learnt in the past few weeks, such as Topic Modeling, Latent Dirichlet Allocation to build a small model analyzing the content of news articles from different sources around the US.

3. In this project you will revisit the sentiment classification task that we did in Assignment 1. However, instead of a BOW classifier, you will build a neural network classifier by fine-tuning a pretrained language model. This approach to building classifiers is the current state-of-the-art, so learning how to do this should set you up very well for many future NLP problems you may want to tackle!

4. In this project you will build a neural machine translation model using a Transformer encoder-decoder architecture. The primary goal of the assignment is to implement the transformer yourself! Outside of this class, you would likely use existing library implementations of Transformers, but for this assignment, we want you to get direct experience with the pieces that go into the full architecture.

5. In this assignment, you'll be implementing a dependency parser using the Shift-Reduce algorithm described in Lecture 17. In Part 1, you'll implement the basic algorithm, with a dummy "oracle" that just uses the ground-truth labels. Then, you'll train a classifier to act as an actual oracle in Part 2, and evaluate the results of that model in Part 3.

Final. For your final project, you will apply concepts you have learned over the semester in order to reproduce a result from a recently published research paper. The goal of this project is to give you a taste of realistic NLP research while providing enough structure to ensure that an interesting result is achievable in the short time frame. You will implement full seq2seq model with attention mentioned in the paper "Language to Logical Form with Neural Attention".
