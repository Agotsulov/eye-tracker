import torch
import dataset
import math
import numpy as np
import os
import logging

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

num_classes = 2
batch_size = 5

log = logging.getLogger("train")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file_handler = logging.FileHandler("train.log")
log_file_handler.setFormatter(formatter)
log.addHandler(log_file_handler)
log_console_handler = logging.StreamHandler()
log.addHandler(log_console_handler)
log.setLevel(logging.INFO)

test_log = logging.getLogger("test")
test_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
test_log_file_handler = logging.FileHandler("train.log")
test_log_file_handler.setFormatter(formatter)
test_log.addHandler(test_log_file_handler)
test_log_file_handler = logging.FileHandler("test.log")
test_log_file_handler.setFormatter(formatter)
test_log.addHandler(test_log_file_handler)
test_log_console_handler = logging.StreamHandler()
test_log.addHandler(test_log_console_handler)
test_log.setLevel(logging.INFO)

val_log = logging.getLogger("val")
val_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
val_log_file_handler = logging.FileHandler("val.log")
val_log_file_handler.setFormatter(formatter)
val_log.addHandler(val_log_file_handler)
val_log_console_handler = logging.StreamHandler()
val_log.addHandler(val_log_console_handler)
val_log.setLevel(logging.INFO)


def train_model(model, seq_len, train_dataset, num_epochs=50, learning_rate=0.001, criterion=None):

    log.info("CURRENT MODEL seq_len: {}".format(seq_len))
    log.info("CURRENT MODEL: {}".format(model.__class__.__name__))
    log.info("CURRENT DATASET SIZE: {}".format(train_dataset.__len__()))

    train_loader = torch.utils.data.DataLoader(dataset=train_dataset,
                                               batch_size=batch_size,
                                               shuffle=True)
    if criterion is None:
        criterion = torch.nn.MSELoss().cuda()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    log.info("TRAIN...")

    total_step = len(train_loader)
    for epoch in range(num_epochs):
        for i, (eye_left, eye_right, face, pos) in enumerate(train_loader):
            eye_left = eye_left.to(device)
            eye_right = eye_right.to(device)
            face = face.to(device)
            pos = pos.to(device)

            # Forward pass
            outputs = model(eye_left, eye_right, face)

            loss = criterion(outputs, pos[:, -1, :])
            # Backward and optimize
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if (i + 1) % 50 == 0:
                log.info('Epoch [{}/{}], Step [{}/{}], Loss: {:.4f}'
                         .format(epoch + 1, num_epochs, i + 1, total_step, loss.item()))

    dirname = './models/{}/'.format(model.__class__.__name__)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    torch.save(model.state_dict(), dirname + 'model_{}.pth'.format(seq_len))
    torch.save(model.state_dict(), dirname + 'model_{}_{}.pth'.format(train_dataset.__len__(), seq_len))
    log.info('Save new model: ' + dirname + 'model_{}_{}.pth'.format(train_dataset.__len__(), seq_len))

    return model


def test_model(model, test_dataset, criterion=None, num_rects=4, screen_w=640, screen_h=480):
    model.eval()

    if criterion is None:
        criterion = torch.nn.MSELoss().cuda()

    print("CURRENT MODEL seq_len: {}".format(test_dataset.seq_len))
    print("CURRENT MODEL: {}".format(model.__class__.__name__))
    print("CURRENT DATASET SIZE: {}".format(test_dataset.__len__()))
    print("CURRENT NUM RECTS: {}".format(num_rects))

    test_loader = torch.utils.data.DataLoader(dataset=test_dataset,
                                               batch_size=batch_size,
                                               shuffle=True)

    min_error = 999999
    max_error = 0
    sum_error = 0
    count_error = 0
    errors = np.zeros(test_dataset.__len__())

    correct = 0
    total = 0

    min_loss = 999999
    max_loss = 0
    sum_loss = 0
    count_loss = 0

    with torch.no_grad():
        for i, (eye_left, eye_right, face, pos) in enumerate(test_loader):
            eye_left = eye_left.to(device)
            eye_right = eye_right.to(device)
            face = face.to(device)
            pos = pos.to(device)

            # Forward pass
            out = model(eye_left, eye_right, face)
            pos = pos[:, -1, :]
            loss = criterion(out, pos)

            out = out.cpu().detach().numpy()
            pos = pos.cpu().numpy()

            for b in range(pos.shape[0]):
                o = out[b]
                p = pos[b]

                error = math.sqrt((o[0] - p[0])**2 + (o[1] - p[1])**2)

                if error < min_error:
                    min_error = error
                if error > max_error:
                    max_error = error
                sum_error += error

                errors[count_error] = error

                o_x = math.ceil((o[0]) / (screen_w / num_rects))
                o_y = math.ceil((o[1]) / (screen_h / num_rects))

                p_x = math.ceil((p[0]) / (screen_w / num_rects))
                p_y = math.ceil((p[1]) / (screen_h / num_rects))


                if ((p_y - 1) * num_rects + (p_x - 1)) == ((o_y - 1) * num_rects + (o_x - 1)):
                    correct += 1

                total += 1

                count_error += 1

            if loss.item() < min_loss:
                min_loss = loss.item()
            if loss.item() > max_loss:
                max_loss = loss.item()
            sum_loss += loss.item()
            count_loss += 1

        print('MIN MSELoss: {} '.format(min_loss))
        print('MAX MSELoss: {} '.format(max_loss))
        print('AVG MSELoss: {}'.format(sum_loss / count_loss))

        print('MIN error: {} '.format(min_error))
        print('MAX error: {} '.format(max_error))
        print('AVG error: {}'.format(sum_error / count_error))
        print('MEAD error: {}'.format(np.median(errors)))

    print('Accuracy : %d %%' % (100 * correct / total))
    return test_dataset.__len__(), min_error, max_error, (sum_error / count_error), (np.median(errors)), errors

def val_model(model, val_dataset):
    model.eval()

    val_log.info("CURRENT MODEL seq_len: {}".format(val_dataset.seq_len))
    val_log.info("CURRENT MODEL: {}".format(model.__class__.__name__))
    val_log.info("CURRENT DATASET SIZE: {}".format(val_dataset.__len__()))

    test_loader = torch.utils.data.DataLoader(dataset=val_dataset,
                                              batch_size=batch_size,
                                              shuffle=True)

    min_error = 999999
    max_error = 0
    sum_error = 0
    count_error = 0
    errors = np.zeros(val_dataset.__len__())

    with torch.no_grad():
        for i, (eye_left, eye_right, face, pos) in enumerate(test_loader):
            eye_left = eye_left.to(device)
            eye_right = eye_right.to(device)
            face = face.to(device)
            pos = pos.to(device)

            out = model(eye_left, eye_right, face)
            pos = pos[:, -1, :]

            out = out.cpu().detach().numpy()
            pos = pos.cpu().numpy()

            for b in range(pos.shape[0]):
                o = out[b]
                p = pos[b]

                error = math.sqrt((o[0] - p[0]) ** 2 + (o[1] - p[1]) ** 2)

                if error < min_error:
                    min_error = error
                if error > max_error:
                    max_error = error
                sum_error += error

                errors[count_error] = error

                count_error += 1

        val_log.info('MIN error: {} '.format(min_error))
        val_log.info('MAX error: {} '.format(max_error))
        val_log.info('AVG error: {}'.format(sum_error / count_error))
        val_log.info('MEAD error: {}'.format(np.median(errors)))

    return val_dataset.__len__(),  min_error, max_error, (sum_error / count_error), (np.median(errors)), errors
