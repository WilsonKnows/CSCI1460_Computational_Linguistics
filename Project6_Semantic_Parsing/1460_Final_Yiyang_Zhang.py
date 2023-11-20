# -*- coding: utf-8 -*-
"""1460 Final Project Semantic Parsing-Yiyang Zhang.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1YLZIVvUmEQSdT_JV3dWIvNaAkwRdKPfJ

# Semantic Parsing Final Project
Link to the paper: https://aclanthology.org/P16-1004.pdf

Read through the paper fully before starting the assignment!
"""

!pip install torch tqdm numpy datasets

import torch
import torch.nn as nn

import torch.nn.init as init
import torch.nn.functional as F
from torch import optim
import random, torch, tqdm

from google.colab import drive
drive.mount('/content/drive')

FILEPATH = "drive/MyDrive/data/"

"""# Data Downloading
This cell obtains the pre-processed Jobs dataset (see the paper) that you will be using to train and evaluate your model. (Pre-processed meaning that argument identification, section 3.6, has already been done for you). You should only need to run this cell ***once***. Feel free to delete it after running. Create a folder in your Google Drive in which the code below will store the pre-processed data needed for this project. Modify `FILEPATH` above to direct to said folder. It should start with `drive/MyDrive/...`, feel free to take a look at previous assignments that use mounting Google Drive if you can't remember what it should look like. *Make sure the data path ends with a slash character ('/').* The below code will access the zip file containing the pre-processed Jobs dataset from the paper and extract the files into your folder! Feel free to take a look at the `train.txt` and `test.txt` files to see what the data looks like. :)
"""

import requests
import io
import zipfile

# https://stackoverflow.com/questions/31126596/saving-response-from-requests-to-file
response = requests.get('http://dong.li/lang2logic/seq2seq_jobqueries.zip')
if response.status_code == 200:
  # https://stackoverflow.com/questions/3451111/unzipping-files-in-python
  with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_ref:
    zip_ref.extractall(FILEPATH)
  print("Extraction completed.")
else:
  print("Failed to download the zip file.")

"""# Data Pre-processing
The following code is defined for you! It extracts the queries (inputs to your Seq2Seq model) and logical forms (expected outputs) from the training and testing files. It also does important pre-processing such as padding the queries and logical forms and turns the words into vocab indices. **Look over and understand this code before you start the assignment!**
"""

def extract_file(filename):
  """
  Extracts queries and corresponding logical forms from either
  train.txt or test.txt. (Feel free to take a look at the files themselves
  in your Drive!)

  Parameters
  ----------
  filename : str
      name of the file to extract from

  Returns
  ----------
  tuple[list[list[str]], list[list[str]]]
      a tuple of a list of queries and their corresponding logical forms
      each in the form of a list of string tokens
  """
  queries, logical_forms = [], []
  with open(FILEPATH + filename) as f:
    for line in f:
      line = line.strip() # remove new line character
      query, logical_form = line.split('\t')

      query = query.split(' ')[::-1] # reversed inputs are used the paper (section 4.2)
      logical_form = ["<s>"] + logical_form.split(' ') + ["</s>"]

      queries.append(query)
      logical_forms.append(logical_form)
  return queries, logical_forms

query_train, lf_train = extract_file('train.txt') # 500 instances
query_test, lf_test = extract_file('test.txt') # 140 instances

from collections import Counter

query_vocab = Counter()
for l in query_train:
  query_vocab.update(l)

query_word2idx = {}
for w, c in query_vocab.items():
  if c >= 2:
    query_word2idx[w] = len(query_word2idx)
query_word2idx['<UNK>'] = len(query_word2idx)
query_word2idx['<PAD>'] = len(query_word2idx)
query_idx2word = {i:word for word,i in query_word2idx.items()}

query_vocab = list(query_word2idx.keys())

lf_vocab = Counter()
for lf in lf_train:
  lf_vocab.update(lf)

lf_vocab['<UNK>'] = 0
lf_vocab['<PAD>'] = 0
lf_idx2word = {i:word for i, word in enumerate(lf_vocab.keys())}
lf_word2idx = {word:i for i, word in lf_idx2word.items()}

query_train_tokens = [[query_word2idx.get(w, query_word2idx['<UNK>']) for w in l] for l in query_train]
query_test_tokens = [[query_word2idx.get(w, query_word2idx['<UNK>']) for w in l] for l in query_test]

lf_train_tokens = [[lf_word2idx.get(w, lf_word2idx['<UNK>']) for w in l] for l in lf_train]
lf_test_tokens = [[lf_word2idx.get(w, lf_word2idx['<UNK>']) for w in l] for l in lf_test]

def pad(seq, max_len, pad_token_idx):
  """
  Pads a given sequence to the max length using the given padding token index

  Parameters
  ----------
  seq : list[int]
      sequence in the form of a list of vocab indices
  max_len : int
      length sequence should be padded to
  pad_token_idx
      vocabulary index of the padding token

  Returns
  ----------
  list[int]
      padded sequence
  """
  seq = seq[:max_len]
  padded_seq = seq + (max_len - len(seq)) * [pad_token_idx]
  return padded_seq

query_max_target_len = max([len(i) for i in query_train_tokens])
query_train_tokens = [pad(i, query_max_target_len, query_word2idx['<PAD>']) for i in query_train_tokens]
query_test_tokens = [pad(i, query_max_target_len, query_word2idx['<PAD>']) for i in query_test_tokens]

lf_max_target_len = int(max([len(i) for i in lf_train_tokens]) * 1.5)
lf_train_tokens = [pad(i, lf_max_target_len, lf_word2idx['<PAD>']) for i in lf_train_tokens]
lf_test_tokens = [pad(i, lf_max_target_len, lf_word2idx['<PAD>']) for i in lf_test_tokens]

"""# Data Loading
The following code creates a JobsDataset and DataLoaders to use with your implemented model. Take a look at the main function at the end of this stencil to see how they are used in context.
"""

from torch.utils.data import Dataset, DataLoader, default_collate

# jobs_train, jobs_test = build_datasets()
# dataloader_train, dataloader_test = build_dataloaders(jobs_train, jobs_test, train_batch_size=20)

class JobsDataset(Dataset):
  """Defines a Dataset object for the Jobs dataset to be used with Dataloader"""
  def __init__(self, queries, logical_forms):
    """
    Initializes a JobsDataset

    Parameters
    ----------
    queries : list[list[int]]
        a list of queries, which have been tokenized and padded, in the form
        of a list of vocab indices
    logical_forms : list[list[int]]
        a list of corresponding logical forms, which have been tokenized and
        padded, in the form of a list of vocab indices
    """
    self.queries = queries
    self.logical_forms = logical_forms

  def __len__(self) -> int:
    """
    Returns the amount of paired queries and logical forms in the dataset

    Returns
    ----------
    int
        length of the dataset
    """
    return len(self.queries)

  def __getitem__(self, idx: int) -> tuple[list[int], list[int]]:
    """
    Returns a paired query and logical form at the specified index

    Parameters
    ----------
    idx : int
        specified index of the dataset

    Returns
    ----------
    tuple[list[int], list[int]]
        paired query and logical form at the specified index, in the form of
        a list of vocab indices
    """
    return self.queries[idx], self.logical_forms[idx]

def build_datasets() -> tuple[JobsDataset, JobsDataset]:
  """
  Builds a train and a test dataset from the queries and logical forms
  train and test tokens

  Returns
  ----------
  tuple[JobsDataset, JobsDataset]
      a training and testing JobsDataset
  """
  jobs_train = JobsDataset(queries=query_train_tokens, logical_forms=lf_train_tokens)
  jobs_test = JobsDataset(queries=query_test_tokens, logical_forms=lf_test_tokens)
  return jobs_train, jobs_test

def collate(batch : list[tuple[list[int], list[int]]]) -> tuple[torch.Tensor, torch.Tensor]:
  """
  Used as collate_fn when creating the Dataloaders from the dataset

  Parameters
  ----------
  batch : list[tuple[list[int], list[int]]]
      a list of outputs of __getitem__

  Returns
  ----------
  tuple[torch.Tensor, torch.Tensor]
      a batched set of input sequences and a batched set of target sequences
  """
  src, tgt = default_collate(batch)
  return torch.stack(src), torch.stack(tgt)

def build_dataloaders(dataset_train: JobsDataset, dataset_test: JobsDataset,
                      train_batch_size: int) -> tuple[DataLoader, DataLoader]:
  """
  Used as collate_fn when creating the Dataloaders from the dataset, batching
  the training data according to the inputted batch size and batching the
  testing data with a batch size of 1

  Parameters
  ----------
  dataset_train : JobsDataset
      training dataset
  dataset_test : JobsDataset
      testing dataset
  train_batch_size : int
      batch size to be used during training

  Returns
  ----------
  tuple[DataLoader, DataLoader]
      a training and testing DataLoader
  """
  dataloader_train = DataLoader(dataset_train, batch_size=train_batch_size, shuffle=True, collate_fn=collate)
  dataloader_test = DataLoader(dataset_test, batch_size=1, shuffle=False, collate_fn=collate)
  return dataloader_train, dataloader_test

"""# Options"""

LF_SOS_INDEX = lf_word2idx['<s>']
LF_EOS_INDEX = lf_word2idx['</s>']
LF_PAD_INDEX = lf_word2idx['<PAD>']

class Options:
    rnn_size = 200
    init_weight = 0.05
    decay_rate = 0.95
    learning_rate = 0.0025 # 0.005 for 5 epochs;
    grad_clip = 5
    dropout = 0
    dropoutrec = 0
    learning_rate_decay =  0.985
    learning_rate_decay_after = 5
    device = "cuda"

opt = Options()

class LSTM(nn.Module):
    def __init__(self, opt):
        """
        Long Short-Term Memory (LSTM) cell implementation.

        Parameters:
        - rnn_size (int): The size of the hidden state and cell state.
        - dropout (float): Dropout probability for regularization.
        """
        super(LSTM, self).__init__()
        self.opt = opt
        self.i2h = nn.Linear(opt.rnn_size, 4 * opt.rnn_size)
        self.h2h = nn.Linear(opt.rnn_size, 4 * opt.rnn_size)
        if opt.dropoutrec > 0:
            self.dropout = nn.Dropout(opt.dropoutrec)

    def forward(self, x, prev_c, prev_h):
        """
        Perform a forward pass through the LSTM cell.

        Parameters
        ----------
        x (Tensor): The input tensor of shape (batch_size, input_size).
        prev_c (Tensor): The previous cell state tensor of shape (batch_size, rnn_size).
        prev_h (Tensor): The previous hidden state tensor of shape (batch_size, rnn_size).

        Returns
        ----------
        cy (Tensor): The updated cell state tensor of shape (batch_size, rnn_size).
        hy (Tensor): The updated hidden state tensor of shape (batch_size, rnn_size).

        """
        gates = self.i2h(x) + self.h2h(prev_h)
        ingate, forgetgate, cellgate, outgate = gates.chunk(4, 1)
        ingate = torch.sigmoid(ingate)
        forgetgate = torch.sigmoid(forgetgate)
        cellgate = torch.tanh(cellgate)
        outgate = torch.sigmoid(outgate)
        if self.opt.dropoutrec > 0:
            cellgate = self.dropout(cellgate)
        cy = (forgetgate * prev_c) + (ingate * cellgate)
        hy = outgate * torch.tanh(cy)  # n_b x hidden_dim
        return cy, hy

"""# RNN Class"""

class RNN(nn.Module):
    def __init__(self, opt, input_size):
        """
        Encoder recurrent neural network (RNN) module.

        Parameters:
        - input_size (int): The size of the input vocabulary.
        - rnn_size (int): The size of the hidden state and cell state.
        - dropout (float): Dropout probability for regularization.
        """
        super(RNN, self).__init__()
        self.opt = opt
        self.hidden_size = opt.rnn_size
        self.embedding = nn.Embedding(input_size, self.hidden_size)
        # self.lstm = LSTM(self.opt)
        self.lstm = nn.LSTM(self.hidden_size, self.hidden_size)
        if opt.dropout > 0:
            self.dropout = nn.Dropout(opt.dropout)

    def forward(self, input_src, prev_c, prev_h):
        """
        Forward pass through the Encoder RNN.

        Parameters:
        - input_src (Tensor): The input tensor of shape (batch_size, sequence_length).
        - prev_c (Tensor): The previous cell state tensor of shape (1, batch_size, rnn_size).
        - prev_h (Tensor): The previous hidden state tensor of shape (1, batch_size, rnn_size).

        Returns:
        - lstm_output (Tensor): The LSTM output tensor of shape (batch_size, sequence_length, rnn_size).
        - (prev_cy, prev_hy) (tuple): Tuple containing updated cell state and hidden state tensors.
          - prev_cy (Tensor): The updated cell state tensor of shape (batch_size, rnn_size).
          - prev_hy (Tensor): The updated hidden state tensor of shape (batch_size, rnn_size).
        """
        src_emb = self.embedding(input_src) # batch_size x src_length x emb_size
        if self.opt.dropout > 0:
            src_emb = self.dropout(src_emb)

        lstm_output, (prev_cy, prev_hy) = self.lstm(src_emb, (prev_c, prev_h))
        return lstm_output, (prev_cy.squeeze(0), prev_hy.squeeze(0))

"""# Attension Union Class"""

class AttnUnit(nn.Module):
    """
    Attention Unit Module for sequence-to-sequence models.

    This module calculates attention weights and produces a prediction based on the
    encoder and decoder hidden states.

    Parameters:
    - opt (argparse.Namespace): Configuration options.
    - output_size (int): Size of the output vocabulary.

    Attributes:
    - opt (argparse.Namespace): Configuration options.
    - hidden_size (int): Size of the hidden state in the encoder and decoder.
    - linear_att (nn.Linear): Linear layer for attention calculation.
    - linear_out (nn.Linear): Linear layer for producing the final output.
    - dropout (nn.Dropout, optional): Dropout layer for regularization.
    - softmax (nn.Softmax): Softmax activation for attention weights.
    - logsoftmax (nn.LogSoftmax): LogSoftmax activation for prediction.

    Methods:
    - forward(enc_s_top, dec_s_top): Forward pass through the attention unit.

    """
    def __init__(self, opt, output_size):
        """
        Initializes the Attention Unit.

        Parameters:
        - opt: Configuration options.
        - output_size (int): Size of the output vocabulary.
        """
        super(AttnUnit, self).__init__()
        self.opt = opt
        self.hidden_size = opt.rnn_size
        # Linear layers for attention and output
        self.linear_att = nn.Linear(2*self.hidden_size, self.hidden_size)
        self.linear_out = nn.Linear(self.hidden_size, output_size)
        # Dropout layer for regularization
        if opt.dropout > 0:
            self.dropout = nn.Dropout(opt.dropout)
        # Activation functions
        self.softmax = nn.Softmax(dim=1)
        self.logsoftmax = nn.LogSoftmax(dim=1)

    def forward(self, enc_s_top, dec_s_top):
        """
        Forward pass through the attention unit.

        Parameters:
        - enc_s_top (torch.Tensor): Encoder hidden states with shape (batch_size, seq_length, hidden_size).
        - dec_s_top (torch.Tensor): Decoder hidden states with shape (batch_size, hidden_size).

        Returns:
        - pred (torch.Tensor): Predicted log probabilities for the output sequence.
        """
        # Calculate attention weights
        dot = torch.bmm(enc_s_top, dec_s_top.unsqueeze(2))
        attention = self.softmax(dot.squeeze(2)).unsqueeze(2)
        # Apply attention to encoder hidden states
        enc_attention = torch.bmm(enc_s_top.permute(0,2,1), attention)
        # Concatenate attention output and decoder hidden state
        hid = F.tanh(self.linear_att(torch.cat((enc_attention.squeeze(2),dec_s_top), 1)))
        h2y_in = hid
        # Apply dropout for regularization
        if self.opt.dropout > 0:
            h2y_in = self.dropout(h2y_in)
        # Produce the final output
        h2y = self.linear_out(h2y_in)
        pred = self.logsoftmax(h2y)
        return pred

"""# Seq2SeqAttentionModel"""

QUERY_VOCAB_LEN = len(query_vocab)
LF_VOCAB_LEN = len(lf_vocab)

# print(QUERY_VOCAB_LEN)
# print(query_vocab)
# print(LF_VOCAB_LEN)
# print(lf_vocab)

class Seq2SeqAttentionModel(nn.Module):
    """
    Sequence-to-Sequence Model with Attention.

    This model comprises an encoder, a decoder, and an attention mechanism for
    sequence-to-sequence tasks.

    Parameters:
    - opt: Configuration options.

    Attributes:
    - encoder (RNN): Encoder module for processing input sequences.
    - decoder (RNN): Decoder module for generating output sequences.
    - attention (AttnUnit): Attention unit for incorporating context information.
    - optimizers (dict): Dictionary containing optimizers for encoder, decoder, and attention.
    - criterion (torch.nn.CrossEntropyLoss): Loss criterion for training.

    Methods:
    - train(): Set the model to training mode.
    - eval(): Set the model to evaluation mode.
    - step(): Perform a gradient descent step for all optimizers.
    - zero_grad(): Zero out the gradients for all optimizers.
    - rate_decay(): Decay the learning rate for all optimizers.
    - grad_clip(): Clip the gradients for all modules based on the specified threshold.

    """
    def __init__(self, opt):
        super(Seq2SeqAttentionModel, self).__init__()
        self.opt = opt
        self.encoder = RNN(self.opt, QUERY_VOCAB_LEN)
        self.decoder = RNN(self.opt, LF_VOCAB_LEN)
        self.attention = AttnUnit(self.opt, LF_VOCAB_LEN)
        self.optimizers = {}
        self.optimizers["encoder_optimizer"] = optim.RMSprop(self.encoder.parameters(), lr=self.opt.learning_rate, alpha=self.opt.decay_rate)
        self.optimizers["decoder_optimizer"] = optim.RMSprop(self.decoder.parameters(), lr=self.opt.learning_rate, alpha=self.opt.decay_rate)
        self.optimizers["attention_optimizer"] = optim.RMSprop(self.attention.parameters(), lr=self.opt.learning_rate, alpha=self.opt.decay_rate)
        self.criterion = nn.NLLLoss(size_average=False, ignore_index=lf_word2idx['<PAD>']) # torch.nn.CrossEntropyLoss(ignore_index=0) # size_average=False,
        self.device = self.opt.device

    # def forward(self, sentence: torch.LongTensor, form: torch.LongTensor, is_eval: bool=False):

    #     cell_en = torch.zeros((sentence.size(1), opt.rnn_size), dtype=torch.float, requires_grad=True).to(sentence.device) # Cell state
    #     hidden_en = torch.zeros((sentence.size(1), opt.rnn_size), dtype=torch.float, requires_grad=True).to(sentence.device) # Hidden state

    #     # Initializae a tensor to store decoder's output
    #     outputs = torch.zeros(form.size(0), form.size(1), LF_VOCAB_LEN).to(self.device) #???

    #     # Last hidden & cell state of the encoder is used as the decoder's initial hidden state
    #     enc_outputs, enc_states = self.encoder(sentence, cell_en.unsqueeze(0), hidden_en.unsqueeze(0))
    #     dec_states = enc_states
    #     decoder_input = torch.tensor([[LF_SOS_INDEX] * sentence.size(1)])

    #     # Predict token by token
    #     for i in range(form.size(0) - 1):
    #         decoder_input = decoder_input.to(sentence.device)
    #         dec_outputs, dec_states = self.decoder(decoder_input, dec_states[0].unsqueeze(0), dec_states[1].unsqueeze(0))
    #         decoder_input = form[i + 1].unsqueeze(0) # Input current target for next interation
    #         outputs[i] = self.attention(enc_outputs.transpose(0, 1), dec_states[0])

    #         # if is_eval:
    #         # # query = query_batch[i].unsqueeze(0) if teacher_forcing else best_pred.unsqueeze(0)
    #         #   value, indice = outputs[i].topk(1)
    #         #   decoder_input = indice.detach()

    #         #   # Break if end-of-sequence token is predicted
    #         #   if indice.item() == LF_EOS_INDEX:
    #         #       break
    #         # else:
    #         #   decoder_input = form[i + 1].unsqueeze(0) # Input current target for next interation

    #     return outputs

    def train(self):
        self.encoder.train()
        self.decoder.train()
        self.attention.train()

    def eval(self):
        self.encoder.eval()
        self.decoder.eval()
        self.attention.eval()

    def step(self):
        for optimizer in self.optimizers:
            self.optimizers[optimizer].step()

    def zero_grad(self):
        for optimizer in self.optimizers:
            self.optimizers[optimizer].zero_grad()

    def rate_decay(self):
        for optimizer in self.optimizers:
            for param_group in self.optimizers[optimizer].param_groups:
                param_group['lr'] = param_group['lr'] * self.opt.learning_rate_decay

    def grad_clip(self):
        torch.nn.utils.clip_grad_value_(self.encoder.parameters(), self.opt.grad_clip)
        torch.nn.utils.clip_grad_value_(self.decoder.parameters(), self.opt.grad_clip)
        torch.nn.utils.clip_grad_value_(self.attention.parameters(), self.opt.grad_clip)

def create_model():

    model = Seq2SeqAttentionModel(opt=opt) # query_vocab_size, lf_vocab_size, hidden_size, output_size
    return model

"""# Training loops"""

LF_SOS_INDEX = lf_word2idx['<s>']
LF_EOS_INDEX = lf_word2idx['</s>']
LF_PAD_INDEX = lf_word2idx['<PAD>']

def train(model: nn.Module, train_dataloader: DataLoader, num_epochs: int=5,
          device: str="cuda") -> nn.Module:
    """
    Trains your model!

    Parameters
    ----------
    model : nn.Module
        your model!
    train_dataloader : DataLoader
        a dataloader of the training data from build_dataloaders
    num_epochs : int
        number of epochs to train for
    device : str
        device that the model is running on

    Returns
    ----------
    nn.Module: Trained Seq2Seq model.

    The training process involves iterating through the specified number of epochs, processing batches of training data,
    and updating the model parameters based on the calculated loss. The training loss is printed after each epoch.
    """
    model = model.to(device)
    print("Training...")

    for epoch in range(num_epochs):
      print("---Epoch {}---\n".format(epoch + 1))
      model.train()

      loss_sum = 0
      for index, (sentence, form) in enumerate(train_dataloader):

          # Zero the gradients to prepare for backpropagation
          model.zero_grad()

          sentence, form = sentence.to(device), form.to(device)

          # Initialize cell and hidden states for the encoder
          cell_en = torch.zeros((sentence.size(1), model.opt.rnn_size), dtype=torch.float, requires_grad=True).to(device)  # Cell state
          hidden_en = torch.zeros((sentence.size(1), model.opt.rnn_size), dtype=torch.float, requires_grad=True).to(device)  # Hidden state

          encoder_outputs, encoder_hidden = model.encoder(sentence, cell_en.unsqueeze(0), hidden_en.unsqueeze(0))

          # Initialize the loss
          loss = 0

          # Initialize the decoder input with the start-of-sequence token
          decoder_input = torch.tensor([[LF_SOS_INDEX] * sentence.size(1)], device=device)
          decoder_hidden = encoder_hidden  # Use the last hidden state from the encoder to start the decoder

          for i in range(form.size(0) - 1):  # Iterate over sequence
              # Generating an output at each time step, and computing attention weights
              # to focus on different parts of the input sequence during the decoding process
              decoder_output, decoder_hidden = model.decoder(decoder_input, decoder_hidden[0].unsqueeze(0), decoder_hidden[1].unsqueeze(0))
              decoder_input = form[i + 1].unsqueeze(0) # Input current target for next interation

              # Calculate attention and accumulate the loss
              pred = model.attention(encoder_outputs.transpose(0, 1), decoder_hidden[0])
              loss += model.criterion(pred.squeeze(0), form[i + 1])
          # logits = model.forward(sentence, form)
          # logits, form = logits.to(device), form.to(device)
          # loss = model.criterion(logits[1:].reshape(-1, logits.shape[-1]), form[1:].reshape(-1)) #!!!
          # loss_sum += loss.item()

          # Average the loss over the batch
          loss = loss / sentence.size(1)
          # Backpropagate the gradients
          loss.backward()

          # Clip gradients if specified
          if model.opt.grad_clip != -1:
              model.grad_clip()

          # Update the model parameters using the optimizer
          model.step()

      # loss_sum = loss.item() / len(train_dataloader)
      loss_sum = loss / len(train_dataloader)

      # Calculate and print the average loss per batch
      print("Average Loss per Batch: {:.4f}\n".format(loss_sum))

      # Decay the learning rate if specified
      if model.opt.learning_rate_decay < 1:
          if epoch >= model.opt.learning_rate_decay_after:
              model.rate_decay()

    return model

"""# Evaluate loops"""

def evaluate(model: nn.Module, dataloader: DataLoader, device: str="cuda") -> tuple[int, int]:
    """
    Evaluates your model!

    Parameters
    ----------
    model : nn.Module
        your model!
    dataloader : DataLoader
        a dataloader of the testing data from build_dataloaders
    device : str
        device that the model is running on model
    Returns
    ----------
    tuple[int, int]
        per-token accuracy and exact_match accuracy

    This function evaluates the model's performance on the given dataloader. It calculates
    the per-token accuracy by comparing the predicted sequence with the target sequence,
    excluding padding tokens. Additionally, it calculates the exact match accuracy by
    checking if all predicted tokens match the target tokens for each sequence.

    The model is expected to have an encoder-decoder architecture with an attention mechanism.
    """

    # for epoch in range(epoch_num):
    print("Predicting..")
    model.eval()
    model.to(device)

    total_tokens = 0
    total_correct = 0
    exact_correct = 0

    with torch.no_grad():

        for sentence, form in dataloader:

            sentence, form = sentence.to(device), form.to(device)

            # Initialize encoder hidden and cell states
            hidden_en = torch.zeros((sentence.size(1), model.opt.rnn_size), dtype=torch.float, requires_grad=True).to(device)  # Hidden state
            cell_en = torch.zeros((sentence.size(1), model.opt.rnn_size), dtype=torch.float, requires_grad=True).to(device)  # Cell state
            # Encode the input sequence
            encoder_outputs, encoder_states = model.encoder(sentence, hidden_en.unsqueeze(0), cell_en.unsqueeze(0))

            # Initialize the first token in the decoder sequence (start-of-sequence)
            prev = torch.tensor([[LF_SOS_INDEX]], device=device) # * sentence.size(1)
            decoder_states = encoder_states

            # Initialize lists to store predicted form and attention weights
            predictions = []

            # Decode the sequence
            for index in range(form.size(0) - 1):
              # Generating an output at each time step, and computing attention weights
              # to focus on different parts of the input sequence during the decoding process
              prev = prev.to(device)
              decoder_output, decoder_states = model.decoder(prev, decoder_states[0].unsqueeze(0), decoder_states[1].unsqueeze(0))
              pred = model.attention(encoder_outputs.transpose(0, 1), decoder_states[0])

              # Choose the token with the highest probability
              value = pred.argmax().item()
              prev = torch.tensor([[value]])
              predictions.append(value)

              # Break if end-of-sequence token is predicted
              if value == LF_EOS_INDEX:
                  break

            # Convert predictions list to a tensor
            predictions = torch.tensor(predictions, device=device)

            # Filter the PADDING terms
            filtered_prediction = [tok for tok in predictions if tok != LF_PAD_INDEX]
            filtered_form = [tok for tok in form[1:, :] if tok != LF_PAD_INDEX]

            # Calculate per-token accuracy
            token_accuracy = [p == t for p, t in zip(filtered_prediction, filtered_form)]
            total_tokens += len(token_accuracy)

            correct_tokens = sum(token_accuracy).item()
            total_correct += correct_tokens

            # Check if all tokens in a sequence are correct for exact match
            exact_correct += int(all(token_accuracy))

        per_token_accuracy = total_correct / total_tokens
        exact_accuracy = exact_correct / len(dataloader.dataset)

    return per_token_accuracy, exact_accuracy

"""# Run this!"""

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    jobs_train, jobs_test = build_datasets()
    dataloader_train, dataloader_test = build_dataloaders(jobs_train, jobs_test, train_batch_size=20)
    # print(dataloader_train) #!!!!!
    model = create_model()
    model = train(model, dataloader_train, num_epochs=5, device="cpu") #device # Epochs = 5
    test_per_token_accuracy, test_exact_match_accuracy = evaluate(model, dataloader_test, device=device)
    print(f'Test Per-token Accuracy: {test_per_token_accuracy}')
    print(f'Test Exact-match Accuracy: {test_exact_match_accuracy}')

main()