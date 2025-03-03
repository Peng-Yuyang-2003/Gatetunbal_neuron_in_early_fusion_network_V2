# train and test the SNN model
import os
from scipy import io
import scipy.io as sio
import numpy as np
import matplotlib.pyplot as plt
import torchvision.datasets
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.quantization import quantize_dynamic
import torchvision.transforms as transforms
from torch.autograd import Variable
from matplotlib.image import imread
from sklearn import preprocessing
from torch import float32
from torch import int64
from torch.utils.data import TensorDataset, random_split
from scipy.io import savemat
data = np.array([])
global mx
global batch_size
mx=8                 # the current ratio of nuerons under -1.5V and 0V
batch_size = 6000    #a batch*2 contains how many samples:12000
print('mx={};batch_size={}'.format(mx,batch_size))
steps=128            #simulation time accurancy
s=28                 #size of photo

# Load audio data
def audiodatabuild():
    global X1,X2   #training set, testing set, data set
    X1 = torch.load('E:/神经元/brain2_learning/Train_audio_data.pt')
    X2 = torch.load('E:/神经元/brain2_learning/Test_audio_data.pt')
    global Y1,Y2   #labels of training set, testing set, data set
    Y1 = torch.load('E:/神经元/brain2_learning/Train_audio_label.pt')
    Y2 = torch.load('E:/神经元/brain2_learning/Test_audio_label.pt')

# Load MNIST data
def download_mnist(data_path, num_train_samples=6000, num_test_samples=1000):
    if not os.path.exists(data_path):
        os.mkdir(data_path)
    transformation = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,), (1.0,))])
    training_set = torchvision.datasets.MNIST(data_path, train=True, transform=transformation, download=True)
    testing_set = torchvision.datasets.MNIST(data_path, train=False, transform=transformation, download=True)
    
    # Randomly subsample the training set to the desired number of samples
    indices = torch.randperm(len(training_set.data))[:num_train_samples]
    training_set.data = training_set.data[indices]
    training_set.targets = training_set.targets[indices]

    # Randomly subsample the testing set to the desired number of samples
    indices = torch.randperm(len(testing_set.data))[:num_test_samples]
    testing_set.data = testing_set.data[indices]
    testing_set.targets = testing_set.targets[indices]
    
    return training_set, testing_set

DATA_PATH = r'E:\\神经元\\MNIST\\Brian2STDPMNIST-master\\MNIST'
training_set, testing_set = download_mnist(DATA_PATH, num_train_samples=60000, num_test_samples=1000)
train_set_loader = torch.utils.data.DataLoader(
    dataset=training_set,
    batch_size=batch_size,
    shuffle=True)
test_set_loader = torch.utils.data.DataLoader(
    dataset=testing_set,
    batch_size=batch_size,
    shuffle=False)

# Input layer: feeding the dataset into the first layer of neurons
class InputDataToSpikingPerceptronLayer(nn.Module):

    def __init__(self, device):
        super(InputDataToSpikingPerceptronLayer, self).__init__()
        self.device = device

        self.reset_state()
        self.to(self.device)

    def reset_state(self):
        #     self.prev_state = torch.zeros([self.n_hidden]).to(self.device)
        pass

    def forward(self, x, is_2D=True):
        x = x.view(x.size(0), -1)  # Flatten 2D image to 1D for FC
        random_activation_perceptron = torch.rand(x.shape).to(self.device)
        return random_activation_perceptron * x

# Input training function
def train(model, device, train_set_loader, optimizer, epoch, multiple, logging_interval=1):
    model.train()
    for batch_idx, (data1, target1) in enumerate(train_set_loader):
        noise = torch.randn(data1.size()) * 0.2
        data1 = data1 + noise
        target1=target1*2 #labels of mnist are even numbers like 0,2,4,6,8...
        data=torch.cat((data1,X1),0) #together
        target=torch.cat((target1,Y1),0) #together
        # differnt gate voltages cause different currents
        for i in range(target.shape[0]):
            if target[i]%2:
                #multiply even rows' current for audio
                data_i = data[i, 0]
                even_indices = torch.arange(0, s, 2)
                even_rows = data_i[even_indices]
                data_i[even_indices] = even_rows * multiple
            else:
                #multiply odd rows' current for mnist
                data_i = data[i, 0]
                odd_indices = torch.arange(1, s, 2)
                odd_rows = data_i[odd_indices]
                data_i[odd_indices] = odd_rows * multiple
        target_remain=target
        target=target//2 #labels of mnist are recovered
        data, target = data.to(device), target.to(device)#put data into device
        optimizer.zero_grad()                            #clear past gradient
        output = model(data)                             #get the probability in prediction
        loss = F.nll_loss(output, target, reduce='mean')                #get value of the loss function
        loss.backward()                                  #backpropagation, calculating the current gradient
        optimizer.step()                                 #update network parameters based on gradients

        if batch_idx % logging_interval == 0:
            pred = output.max(1, keepdim=True)[1]  # get the index of the max probability in prediction
            correct = pred.eq(target.view_as(pred)).float().mean().item()
            print('Train Epoch: {} [{}/{} ({:.0f}%)] Loss: {:.6f} Accuracy: {:.2f} %'.format(
                epoch, batch_idx * len(data), 2*len(train_set_loader.dataset),
                100. * batch_idx / (len(train_set_loader)), loss.item(),
                100. * correct)) 
            data = data.cpu().numpy()
            data = np.append(data,  loss.cpu().item())
            #test(model, device, test_set_loader,multiple=mx) # get accurancy on testing set
        epoch+=1  

# Input Test Functions
def test(model, device, test_set_loader, multiple):

    model.eval()
    test_loss = 0
    correct = 0

    #mnist accurancy
    with torch.no_grad():
        for data1, target1 in test_set_loader:
            target1=target1*2
            data=data1
            target20=target1
            for i in range(target20.shape[0]):
                if target20[i]%2:
                    data_i = data[i, 0]
                    even_indices = torch.arange(0, s, 2)
                    even_rows = data_i[even_indices]
                    data_i[even_indices] = even_rows * multiple
                else:
                    data_i = data[i, 0]
                    odd_indices = torch.arange(1, s, 2)
                    odd_rows = data_i[odd_indices]
                    data_i[odd_indices] = odd_rows * multiple
            target=target20//2
            data, target = data.to(device), target.to(device)
            output = model(data)
            pred = output.max(1, keepdim=True)[1]                         #get the index of the max probability in prediction
            '''
            #confusion matrix
            targetnumpy = np.array(target)
            prednumpy = np.array(pred.squeeze())
            confusion_matrix = np.zeros((10, 10))
            for i in range(10):
                for j in range(10):
                    confusion_matrix[i, j] = np.sum((prednumpy == j) & (targetnumpy == i))
            confusion_matrix_norm = confusion_matrix / np.sum(confusion_matrix, axis=1)
            io.savemat('confusion_matrix_best_iamge-2V.mat', {'matrix': confusion_matrix_norm})
            fig, ax = plt.subplots()
            im = ax.imshow(confusion_matrix_norm, cmap='Blues')
            for i in range(confusion_matrix_norm.shape[0]):
                for j in range(confusion_matrix_norm.shape[1]):
                    text = ax.text(j, i, round((confusion_matrix_norm[i,j]),2),
                                ha="center", va="center", color="r")
            plt.colorbar(im, ax=ax)
            ax.set_xlabel('Predicted labels')
            ax.set_ylabel('True labels')
            plt.show()
            '''
            correct += pred.eq(target.view_as(pred)).sum().item()

    #audio accurancy
    with torch.no_grad():
        for data1, target1 in test_set_loader:
            target1=target1*2
            data=X2
            target20=Y2
            for i in range(target20.shape[0]):
                if target20[i]%2:
                    data_i = data[i, 0]
                    even_indices = torch.arange(0, s, 2)
                    even_rows = data_i[even_indices]
                    data_i[even_indices] = even_rows * multiple
                else:
                    data_i = data[i, 0]
                    odd_indices = torch.arange(1, s, 2)
                    odd_rows = data_i[odd_indices]
                    data_i[odd_indices] = odd_rows * multiple
            target=target20//2
            data, target = data.to(device), target.to(device)
            output = model(data)
            pred = output.max(1, keepdim=True)[1]                         #get the index of the max probability in prediction
            '''
            #confusion matrix
            targetnumpy = np.array(target)
            prednumpy = np.array(pred.squeeze())
            confusion_matrix = np.zeros((10, 10))
            for i in range(10):
                for j in range(10):
                    confusion_matrix[i, j] = np.sum((prednumpy == j) & (targetnumpy == i))
            confusion_matrix_norm = confusion_matrix / np.sum(confusion_matrix, axis=1)
            io.savemat('confusion_matrix_best_audio-2V.mat', {'matrix': confusion_matrix_norm})
            fig, ax = plt.subplots()
            im = ax.imshow(confusion_matrix_norm, cmap='Blues')
            for i in range(confusion_matrix_norm.shape[0]):
                for j in range(confusion_matrix_norm.shape[1]):
                    text = ax.text(j, i, round((confusion_matrix_norm[i,j]),2),
                                ha="center", va="center", color="r")
            plt.colorbar(im, ax=ax)
            ax.set_xlabel('Predicted labels')
            ax.set_ylabel('True labels')
            plt.show()
            '''
            correct += pred.eq(target.view_as(pred)).sum().item()
    print('Test set: Accuracy: {}/{} ({:.2f}%)'.format(
        correct, 2*len(test_set_loader.dataset),
        100. * correct / (2*len(test_set_loader.dataset))))


# Neural networks at all layers
# backward propagation of impulse input test functions with synapses as subjects
class SpikingNeuronLayerSNN(nn.Module):

    def __init__(self, device, n_inputs=28*28, n_hidden=100, decay_multiplier=0.8, threshold=2.0, penalty_threshold=2.5):
        super(SpikingNeuronLayerSNN, self).__init__()
        self.device = device
        self.n_inputs = n_inputs
        self.n_hidden = n_hidden
        self.decay_multiplier = decay_multiplier
        self.threshold = threshold
        self.penalty_threshold = penalty_threshold
        self.fc = nn.Linear(n_inputs, n_hidden)

        self.init_parameters()
        self.reset_state()
        self.to(self.device)

    def init_parameters(self):
        for param in self.parameters():
            if param.dim() >= 2:
                nn.init.xavier_uniform_(param)

    def reset_state(self):
        self.prev_inner = torch.zeros([self.n_hidden]).to(self.device)
        self.prev_outer = torch.zeros([self.n_hidden]).to(self.device)

    def forward(self, x):
        """
        Call the neuron at every time step.
        x: activated_neurons_below
        return: a tuple of (state, output) for each time step. Each item in the tuple
        are then themselves of shape (batch_size, n_hidden) and are PyTorch objects, such
        that the whole returned would be of shape (2, batch_size, n_hidden) if casted.
        """
        if self.prev_inner.dim() == 1:
            # saving pre-state before reset the layer
            # Adding batch_size dimension directly after doing a `self.reset_state()`:
            batch_size = x.shape[0]
            self.prev_inner = torch.stack(batch_size * [self.prev_inner])
            self.prev_outer = torch.stack(batch_size * [self.prev_outer])
        #aaaaaaaaaaa
        # Quantize and dequantize the weights of layer1
        #quantized_weight = torch.quantize_per_tensor(self.fc.weight, scale=0.0001, zero_point=0, dtype=torch.qint8)
        #dequantized_weight = quantized_weight.dequantize()

        # Replace original weight with dequantized weight
        #original_weight = self.fc.weight
        #self.fc.weight = nn.Parameter(dequantized_weight)

        # 1. Weight matrix multiplies the input x
        input_excitation = self.fc(x)

        # 2. We add the result to a decayed version of the information we already had.
        inner_excitation = input_excitation + self.prev_inner * self.decay_multiplier

        # 3. We compute the activation of the neuron to find its output value,
        #    but before the activation, there is also a negative bias that refrain thing from firing too much.
        outer_excitation = F.relu(inner_excitation - self.threshold)

        # 4. If the neuron fires, the activation of the neuron is subtracted to its inner state
        #    (and with an extra penalty for increase refractory time),
        #    because it discharges naturally so it shouldn't fire twice.
        do_penalize_gate = (outer_excitation > 0).float()
        #    neuron function
        inner_excitation = inner_excitation - (self.penalty_threshold/self.threshold * inner_excitation) * do_penalize_gate

        # 5. The outer excitation has a negative part after the positive part.
        outer_excitation = outer_excitation #+ torch.abs(self.prev_outer) * self.decay_multiplier / 2.0

        # 6. Setting internal values before returning.
        #    And the returning value is the one of the previous time step to delay
        #    activation of 1 time step of "processing" time. For logits, we don't take activation.
        delayed_return_state = self.prev_inner
        delayed_return_output = self.prev_outer
        self.prev_inner = inner_excitation
        self.prev_outer = outer_excitation
        #aaaaaaaaaaa
        #self.fc.weight = original_weight
        return delayed_return_state, delayed_return_output

# Output layer: gives a record of the output impulses of the last layer of neurons
class OutputDataToSpikingPerceptronLayer(nn.Module):

    def __init__(self, average_output=True):
        super(OutputDataToSpikingPerceptronLayer, self).__init__()
        if average_output:
            self.reducer = lambda x, dim: x.sum(dim=dim)
        else:
            self.reducer = lambda x, dim: x.mean(dim=dim)

    def forward(self, x):
        if type(x) == list:
            x = torch.stack(x)
        return self.reducer(x, 0)

# Build an entire impulse neural network
class SpikingNet(nn.Module):

    def __init__(self, device, n_time_steps, begin_eval):
        super(SpikingNet, self).__init__()
        assert (0 <= begin_eval and begin_eval < n_time_steps)
        self.device = device
        self.n_time_steps = n_time_steps
        self.begin_eval = begin_eval

        self.input_conversion = InputDataToSpikingPerceptronLayer(device)

        self.layer1 = SpikingNeuronLayerSNN(
            device, n_inputs=28*28, n_hidden=100,
            decay_multiplier=0.9, threshold=2.0, penalty_threshold=2.0
        )

        self.layer2 = SpikingNeuronLayerSNN(
            device, n_inputs=100, n_hidden=10,
            decay_multiplier=0.9, threshold=2.0, penalty_threshold=2.0
        )

        self.output_conversion = OutputDataToSpikingPerceptronLayer(average_output=False)  # Sum on outputs.

        self.to(self.device)

    def forward_through_time(self, x):
        """
        This acts as a layer. Its input is non-time-related, and its output too.
        So the time iterations happens inside, and the returned layer is thus
        passed through global average pooling on the time axis before the return
        such as to be able to mix this pipeline with regular backprop layers such
        as the input data and the output data.
        """
        self.input_conversion.reset_state()
        self.layer1.reset_state()
        self.layer2.reset_state()

        out = []

        all_layer1_states = []
        all_layer1_outputs = []
        all_layer2_states = []
        all_layer2_outputs = []
        for _ in range(self.n_time_steps):
            xi = self.input_conversion(x)
            #print(xi.size())
            # For layer 1, we take the regular output.
            layer1_state, layer1_output = self.layer1(xi)
            #layer1_output=torch.mul(layer1_output,layer1_state) it can be changed
            # We take inner state of layer 2 because it's pre-activation and thus acts as out logits.
            layer2_state, layer2_output = self.layer2(layer1_output)

            all_layer1_states.append(layer1_state)
            all_layer1_outputs.append(layer1_output)
            all_layer2_states.append(layer2_state)
            all_layer2_outputs.append(layer2_output)
            out.append(layer2_state)

        out = self.output_conversion(out[self.begin_eval:])
        return out, [[all_layer1_states, all_layer1_outputs], [all_layer2_states, all_layer2_outputs]]

    def forward(self, x):
        out, _ = self.forward_through_time(x)
        return F.log_softmax(out, dim=-1)
    # visualization functions
    def visualize_all_neurons(self, x):
        assert x.shape[0] == 1 and len(x.shape) == 4, (
            "Pass only 1 example to SpikingNet.visualize(x) with outer dimension shape of 1.")
        _, layers_state = self.forward_through_time(x)

        for i, (all_layer_states, all_layer_outputs) in enumerate(layers_state):
            layer_state  =  torch.stack(all_layer_states).data.cpu().numpy().squeeze().transpose()
            layer_output = torch.stack(all_layer_outputs).data.cpu().numpy().squeeze().transpose()
            sio.savemat('E:\神经元\\brain2_learning\\layer-state{}.mat'.format(i), {'matrix':layer_state})
            sio.savemat('E:\神经元\\brain2_learning\\layer-output{}.mat'.format(i), {'matrix':layer_output})

            self.plot_layer(layer_state, title="Inner state values of neurons for layer {}".format(i))
            self.plot_layer(layer_output, title="Output spikes (activation) values of neurons for layer {}".format(i))

    def visualize_neuron(self, x, layer_idx, neuron_idx):
        assert x.shape[0] == 1 and len(x.shape) == 4, (
            "Pass only 1 example to SpikingNet.visualize(x) with outer dimension shape of 1.")
        _, layers_state = self.forward_through_time(x)

        all_layer_states, all_layer_outputs = layers_state[layer_idx]
        layer_state  =  torch.stack(all_layer_states).data.cpu().numpy().squeeze().transpose()
        layer_output = torch.stack(all_layer_outputs).data.cpu().numpy().squeeze().transpose()

        self.plot_neuron(layer_state[neuron_idx], title="Inner state values neuron {} of layer {}".format(neuron_idx, layer_idx))
        self.plot_neuron(layer_output[neuron_idx], title="Output spikes (activation) values of neuron {} of layer {}".format(neuron_idx, layer_idx))

    def plot_layer(self, layer_values, title):
        width = max(16, layer_values.shape[0] / 8)
        height = max(4, layer_values.shape[1] / 8)
        plt.figure(figsize=(width, height))
        plt.imshow(
            layer_values,
            interpolation="nearest",
            cmap=plt.cm.rainbow
        )
        plt.title(title)
        plt.colorbar()
        plt.xlabel("Time")
        plt.ylabel("Neurons of layer")
        plt.show()

    def plot_neuron(self, neuron_through_time, title):
        width = max(16, len(neuron_through_time) / 8)
        height = 4
        plt.figure(figsize=(width, height))
        plt.title(title)
        plt.plot(neuron_through_time)
        plt.xlabel("Time")
        plt.ylabel("Neuron's activation")
        plt.show()

    def visualize_weights(self): 
        tensor_transposed1 = self.layer1.fc.weight
        sio.savemat('weight_tensor2_784_to_100.mat', {'weight_tensor':tensor_transposed1.detach().numpy()})
        fig, ax = plt.subplots()
        im = ax.imshow(tensor_transposed1.detach().numpy(), cmap='Blues')
        plt.colorbar(im, ax=ax)
        ax.set_xlabel('input')
        ax.set_ylabel('neurons')
        plt.show()
        tensor_transposed2 = self.layer2.fc.weight
        sio.savemat('weight_tensor2_100_to_10.mat', {'weight_tensor': tensor_transposed2.detach().numpy()})
        fig, ax = plt.subplots()
        im = ax.imshow(tensor_transposed2.detach().numpy(), cmap='Blues')
        plt.colorbar(im, ax=ax)
        ax.set_xlabel('neurons')
        ax.set_ylabel('neurons')
        plt.show()

# Parameter tuning functions for training and testing
def train_many_epochs(model):
    epoch = 1
    optimizer = optim.SGD(model.parameters(), lr=0.02, momentum=0.5)
    for epoch in range(1, 6):
        mx= epoch + 3 # in training process ,we need mx gradually reaches 8
        train(model, device, train_set_loader, optimizer, epoch, multiple=mx,logging_interval=1)
    #test(model, device, test_set_loader,multiple=mx)

    #epoch = 61
    #optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.5)
    #train(model, device, train_set_loader, optimizer, epoch, multiple=mx,logging_interval=10)
    test(model, device, test_set_loader,multiple=mx)
    torch.save(model.state_dict(), "spiking_model_weights.pth")
    
use_cuda = torch.cuda.is_available()# use GPU when possible
device = torch.device("cuda" if use_cuda else "cpu")

# main function
audiodatabuild()
spiking_model = SpikingNet(device, n_time_steps=steps, begin_eval=0)

def load_model_and_train(model_path):
    model = SpikingNet(device, n_time_steps=steps, begin_eval=0)
    model.load_state_dict(torch.load(model_path))
    train_many_epochs(model)
def load_model_and_infer(model_path):
    model = SpikingNet(device, n_time_steps=steps, begin_eval=0)
    model.load_state_dict(torch.load(model_path))
    test(model, device, test_set_loader,multiple=mx)
model_path = "spiking_model_quantized_weights.pth"
#train_many_epochs(spiking_model) #first training, save in spiking_model_weights.pth
#spiking_model = load_model_and_train(model_path) #load and train, save in spiking_model_weights.pth
spiking_model = load_model_and_infer(model_path) #load and test, before this, use test_quantize.py to quantize the model and save in spiking_model_quantized_weights.pth

#mat_data = {'train_loss': data}
#savemat('trainloss.mat', mat_data)
'''

#visualize the input data
m=0
data, target = test_set_loader.__iter__().__next__()
for i in range(0,200):
    if target.data.numpy()[i]==9:
        m=m+1
        x = torch.stack([data[i]]) #torch.stack([data[i]])
        y= torch.stack([target[i]])
        sio.savemat('E:\JisuCloud\matrix_number_mnist\\Number-{}-audio-{}.mat'.format(y[0],m-1), {'matrix':x.detach().numpy()[0,0]})
        if(m==10):
            break
        plt.figure(figsize=(12,12))
        plt.imshow(x.data.cpu().numpy()[0,0])
        plt.title("Input image x of label y={}:".format(y))
        plt.show()

for i in range(1200,1210):
    x=torch.stack([X[i]])
    y=torch.stack([Y[i]])
    sio.savemat("E:\JisuCloud\matrix_number_audio\\Number-{}-audio-{}.mat".format(8,i-1200), {'matrix':x.detach().numpy()[0,0]})
'''


#visualize the weights of the model
#spiking_model.visualize_weights()
'''
#可视化脉冲机制
# taking 1st testing example
data, target = test_set_loader.__iter__().__next__()

x = torch.stack([data[0]]) 
y = target.data.numpy()[0]
plt.figure(figsize=(12,12))
plt.imshow(x.data.cpu().numpy()[0,0])
plt.title("Input image x of label y={}:".format(y))
plt.show()

spiking_model.visualize_all_neurons(x) # plotting neuron's activations:

print("A hidden neuron that looks excited:")
spiking_model.visualize_neuron(x, layer_idx=0, neuron_idx=0)
print("The output neuron of the label:")
spiking_model.visualize_neuron(x, layer_idx=1, neuron_idx=y)
'''
