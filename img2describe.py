import argparse
import json
import pickle
import random
from hashlib import md5
from urllib.parse import quote
from urllib.request import urlopen

import torch
from PIL import Image
from torchvision import transforms

from model import EncoderCNN, DecoderRNN

# Device configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def load_image(image_path, transform=None):
    image = Image.open(image_path).convert('RGB')
    image = image.resize([224, 224], Image.LANCZOS)

    if transform is not None:
        image = transform(image).unsqueeze(0)

    return image


def translate(word):
    appid = '20200311000396087'
    secretkey = 'qdix1LSHL95rf9Oyfujq'
    salt = random.randint(23456, 56789)
    q = quote(word)

    s = appid + word + str(salt) + secretkey
    m = md5()
    m.update(s.encode('utf-8'))
    sign = m.hexdigest()

    url = 'http://api.fanyi.baidu.com/api/trans/vip/translate?q=' + q + '&from=en&to=zh&appid=' + appid + '&salt=' + str(
        salt) + '&sign=' + sign

    url_word = urlopen(url)
    read_word = url_word.read().decode('utf-8')
    json_word = json.loads(read_word)
    # print(json_word)
    t_word = json_word['trans_result'][0]['dst']
    # print(t_word)
    return t_word


def img2txt(args):
    # Image preprocessing
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406),
                             (0.229, 0.224, 0.225))])

    # Load vocabulary wrapper
    with open(args['vocab_path'], 'rb') as f:
        vocab = pickle.load(f)

    # Build models
    encoder = EncoderCNN(args['embed_size']).eval()  # eval mode (batchnorm uses moving mean/variance)
    decoder = DecoderRNN(args['embed_size'], args['hidden_size'], len(vocab), args['num_layers'])
    encoder = encoder.to(device)
    decoder = decoder.to(device)

    # Load the trained model parameters
    encoder.load_state_dict(torch.load(args['encoder_path']))
    decoder.load_state_dict(torch.load(args['decoder_path']))

    # Prepare an image
    image = load_image(args['image'], transform)
    image_tensor = image.to(device)

    # Generate an caption from the image
    feature = encoder(image_tensor)
    sampled_ids = decoder.sample(feature)
    sampled_ids = sampled_ids[0].cpu().numpy()  # (1, max_seq_length) -> (max_seq_length)

    # Convert word_ids to words
    sampled_caption = []
    for word_id in sampled_ids:
        word = vocab.idx2word[word_id]
        sampled_caption.append(word)
        if word == '<end>':
            break
    sentence = ' '.join(sampled_caption).lstrip('<start>').rstrip('<end>').strip()

    # Print out the image and the generated caption
    print(sentence)
    return f'[这个图翻译如下]:\n{sentence}\n{translate(sentence)}'
    # image = Image.open(args.image)
    # plt.imshow(np.asarray(image))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=str, required=True, help='input image for generating caption')
    parser.add_argument('--encoder_path', type=str, default='models/encoder-5-3000.ckpt',
                        help='path for trained encoder')
    parser.add_argument('--decoder_path', type=str, default='models/decoder-5-3000.ckpt',
                        help='path for trained decoder')
    parser.add_argument('--vocab_path', type=str, default='data/vocab.pkl', help='path for vocabulary wrapper')

    # Model parameters (should be same as paramters in train.py)
    parser.add_argument('--embed_size', type=int, default=256, help='dimension of word embedding vectors')
    parser.add_argument('--hidden_size', type=int, default=512, help='dimension of lstm hidden states')
    parser.add_argument('--num_layers', type=int, default=1, help='number of layers in lstm')
    args_ = parser.parse_args()
    img2txt(args_)
