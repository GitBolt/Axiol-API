import os
import numpy
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from pymongo import MongoClient

from model import NeuralNet
from utils import tokenize_and_lemmatize, bag_of_words

MONGO_TRAINING_URL = MongoClient(os.environ.get("MONGO_TRAINING_URL"))
DB1 = MONGO_TRAINING_URL["DB1"] 
collection1 = DB1.get_collection("Col1")
document1 = collection1.find_one({"_id": 1})
alldata = list(collection1.find())

all_words = []
tags = []
xy = []

for data in alldata:
    tag = data['tag']
    tags.append(tag)
    for pattern in data['patterns']:
        w = tokenize_and_lemmatize(pattern)
        all_words.extend(w)
        xy.append((w, tag))
        
# create training data
ignored_chars = ['?','!', ',', ';', ':']
all_words = [x for x in all_words if not x in ignored_chars]
#Remove duplicates and sort
all_words = sorted(set(all_words)) 
print(all_words)
tags = sorted(set(tags))

print(f"{len(xy)} Patterns\n\n{len(tags)} Tags: {tags}")

X_train = []
y_train = []
for (pattern_sentence, tag) in xy:
    # X: bag of words for each pattern_sentence
    bag = bag_of_words(pattern_sentence, all_words)
    X_train.append(bag)
    # y: PyTorch CrossEntropyLoss needs only class labels, not one-hot
    label = tags.index(tag)
    y_train.append(label)

X_train = numpy.array(X_train)
y_train = numpy.array(y_train)

# Hyper-parameters 
num_epochs = 1000
batch_size = 8
learning_rate = 0.001
input_size = len(X_train[0])
hidden_size = 8
output_size = len(tags)
print(input_size, output_size)

class ChatDataset(Dataset):

    def __init__(self):
        self.n_samples = len(X_train)
        self.x_data = X_train
        self.y_data = y_train

    # support indexing such that dataset[i] can be used to get i-th sample
    def __getitem__(self, index):
        return self.x_data[index], self.y_data[index]

    # we can call len(dataset) to return the size
    def __len__(self):
        return self.n_samples

dataset = ChatDataset()
train_loader = DataLoader(dataset=dataset,
                          batch_size=batch_size,
                          shuffle=True,
                          num_workers=0)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = NeuralNet(input_size, hidden_size, output_size).to(device)

# Loss and optimizer
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

# Train the model
for epoch in range(num_epochs):
    for (words, labels) in train_loader:
        words = words.to(device)
        labels = labels.to(dtype=torch.long).to(device)
        
        # Forward pass
        outputs = model(words)
        # if y would be one-hot, we must apply
        # labels = torch.max(labels, 1)[1]
        loss = criterion(outputs, labels)
        
        # Backward and optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
    if (epoch+1) % 100 == 0:
        print (f'Epoch [{epoch+1}/{num_epochs}], Loss: {loss.item():.4f}')


print(f'final loss: {loss.item():.4f}')

data = {
"model_state": model.state_dict(),
"input_size": input_size,
"hidden_size": hidden_size,
"output_size": output_size,
"all_words": all_words,
"tags": tags
}

FILE = "data.pth"
torch.save(data, FILE)

print(f'File saved to {FILE}')
