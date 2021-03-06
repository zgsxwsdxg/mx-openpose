#encoding=utf-8
'''
@Author: kohill
'''
import sys,os,math
import mxnet as mx
import cv2 
import numpy as np
from train import numoflinks,numofparts
debug = False
# %matplotlib inline
import pylab as plt
search_ratio = [1]
imgshape_bind = [(int(368*x),int(368*x)) for x in search_ratio]
max_img_shape = (int(max(search_ratio)*368),int(max(search_ratio)*368))

def padimg(img,destsize):
    s = img.shape
    if(s[0] > s[1]):
        img_d = cv2.resize(img,dsize = None,fx = 1.0 * destsize/s[0], fy = 1.0 * destsize/s[0])
        img_temp = np.ones(shape = (destsize,destsize,3),dtype=np.uint8) * 128
        sd = img_d.shape
        img_temp[0:sd[0],0:sd[1],0:sd[2]]=img_d
    else:
        img_d = cv2.resize(img,dsize = None,fx = 1.0 * destsize/s[1],fy = 1.0 * destsize/s[1])
        img_temp = np.ones(shape = (destsize,destsize,3),dtype=np.uint8) * 128 
        sd = img_d.shape
        img_temp[0:sd[0],0:sd[1],0:sd[2]]=img_d
    return img_temp

def parse_heatpaf(oriImg,heatmap_avg,paf_avg):
    

    '''
    0：头顶
    1：脖子
    2：右肩
    3：右肘
    4：右腕

    '''
        

        
    param={}
 
    param['thre1'] = 0.2
    param['thre2'] = 0.1
    param['mid_num'] = 7


    import scipy

    #plt.imshow(heatmap_avg[:,:,2])
    from scipy.ndimage.filters import gaussian_filter
    all_peaks = []
    peak_counter = 0

    
    for part in range(15-1):
        x_list = []
        y_list = []
        map_ori = heatmap_avg[:,:,part]
        map = gaussian_filter(map_ori, sigma=3)
        #map = map_ori
        map_left = np.zeros(map.shape)
        map_left[1:,:] = map[:-1,:]
        map_right = np.zeros(map.shape)
        map_right[:-1,:] = map[1:,:]
        map_up = np.zeros(map.shape)
        map_up[:,1:] = map[:,:-1]
        map_down = np.zeros(map.shape)
        map_down[:,:-1] = map[:,1:]
        
        peaks_binary = np.logical_and.reduce((map>=map_left, map>=map_right, map>=map_up, map>=map_down, map > param['thre1']))
        peaks = zip(np.nonzero(peaks_binary)[1], np.nonzero(peaks_binary)[0]) # note reverse
        peaks_with_score = [x + (map_ori[x[1],x[0]],) for x in peaks]
        id = range(peak_counter, peak_counter + len(peaks))
        peaks_with_score_and_id = [peaks_with_score[i] + (id[i],) for i in range(len(id))]

        all_peaks.append(peaks_with_score_and_id)
        peak_counter += len(peaks)
    # find connection in the specified sequence, center 29 is in the position 15
    limbSeq = [[13, 14], [14, 1], [14, 4], [1, 2], [2, 3], [4, 5], [5, 6], [1, 7], [7, 8],
            [8, 9], [4, 10], [10, 11], [11, 12]]
    # the middle joints heatmap correpondence
    mapIdx = [(i*2,i*2+1) for i in range(numoflinks)]
    assert(len(limbSeq) == numoflinks ) 

    connection_all = []
    special_k = []
    special_non_zero_index = []
    mid_num = param['mid_num'] 
#     if debug:
#     pydevd.settrace("127.0.0.1", True, True, 5678, True) 
    for k in range(len(mapIdx)):
        score_mid = paf_avg[:,:,[x for x in mapIdx[k]]]
        candA = all_peaks[limbSeq[k][0]-1]
        candB = all_peaks[limbSeq[k][1]-1]
        # print(k)
        # print(candA)
        # print('---------')
        # print(candB)
        nA = len(candA)
        nB = len(candB)
        indexA, indexB = limbSeq[k]
        if(nA != 0 and nB != 0):
            connection_candidate = []
            for i in range(nA):
                for j in range(nB):
                    vec = np.subtract(candB[j][:2], candA[i][:2])
                    # print('vec: ',vec)
                    norm = math.sqrt(vec[0]*vec[0] + vec[1]*vec[1])
                    # print('norm: ', norm)
                    vec = np.divide(vec, norm)
                    # print('normalized vec: ', vec)
                    startend = zip(np.linspace(candA[i][0], candB[j][0], num=mid_num), \
                                np.linspace(candA[i][1], candB[j][1], num=mid_num))
                    # print('startend: ', startend)
                    vec_x = np.array([score_mid[int(round(startend[I][1])), int(round(startend[I][0])), 0] \
                                    for I in range(len(startend))])
                    # print('vec_x: ', vec_x)
                    vec_y = np.array([score_mid[int(round(startend[I][1])), int(round(startend[I][0])), 1] \
                                    for I in range(len(startend))])
                    # print('vec_y: ', vec_y)
                    score_midpts = np.multiply(vec_x, vec[0]) + np.multiply(vec_y, vec[1])
                    # print(score_midpts)
                    # print('score_midpts: ', score_midpts)
                    try:
                        score_with_dist_prior = sum(score_midpts)/len(score_midpts) + min(0.5*oriImg.shape[0]/norm-1, 0)
                    except ZeroDivisionError:
                        score_with_dist_prior = -1               
                    ##print('score_with_dist_prior: ', score_with_dist_prior)
                    criterion1 = len(np.nonzero(score_midpts > param['thre2'])[0]) > 0.8 * len(score_midpts)
                    # print('score_midpts > param["thre2"]: ', len(np.nonzero(score_midpts > param['thre2'])[0]))
                    criterion2 = score_with_dist_prior > 0
                    
                    if criterion1 and criterion2:
                        # print('match')
                        # print(i, j, score_with_dist_prior, score_with_dist_prior+candA[i][2]+candB[j][2])
                        connection_candidate.append([i, j, score_with_dist_prior, score_with_dist_prior+candA[i][2]+candB[j][2]])
                    # print('--------end-----------')
            connection_candidate = sorted(connection_candidate, key=lambda x: x[2], reverse=True)
            # print('-------------connection_candidate---------------')
            # print(connection_candidate)
            # print('------------------------------------------------')
            connection = np.zeros((0,5))
            for c in range(len(connection_candidate)):
                i,j,s = connection_candidate[c][0:3]
                if(i not in connection[:,3] and j not in connection[:,4]):
                    connection = np.vstack([connection, [candA[i][3], candB[j][3], s, i, j]])
                    # print('----------connection-----------')
                    # print(connection)
                    # print('-------------------------------')
                    if(len(connection) >= min(nA, nB)):
                        break

            connection_all.append(connection)
        elif(nA != 0 or nB != 0):
            special_k.append(k)
            special_non_zero_index.append(indexA if nA != 0 else indexB)
            connection_all.append([])
    # last number in each row is the total parts number of that person
    # the second last number in each row is the score of the overall configuration
    subset = -1 * np.ones((0, 20))

    candidate = np.array([item for sublist in all_peaks for item in sublist])


    for k in range(len(mapIdx)):
        if k not in special_k:
            try:
                partAs = connection_all[k][:,0]
                partBs = connection_all[k][:,1]
                indexA, indexB = np.array(limbSeq[k]) - 1
            except IndexError as e :
                row = -1 * np.ones(20)
                subset = np.vstack([subset, row])        
                continue
            except TypeError as e:
                row = -1 * np.ones(20)
                subset = np.vstack([subset, row])        
                continue
            for i in range(len(connection_all[k])): #= 1:size(temp,1)
                found = 0
                subset_idx = [-1, -1]
                for j in range(len(subset)): #1:size(subset,1):
                    if subset[j][indexA] == partAs[i] or subset[j][indexB] == partBs[i]:
                        subset_idx[found] = j
                        found += 1
                
                if found == 1:
                    j = subset_idx[0]
                    if(subset[j][indexB] != partBs[i]):
                        subset[j][indexB] = partBs[i]
                        subset[j][-1] += 1
                        subset[j][-2] += candidate[partBs[i].astype(int), 2] + connection_all[k][i][2]
                elif found == 2: # if found 2 and disjoint, merge them
                    j1, j2 = subset_idx
                    print "found = 2"
                    membership = ((subset[j1]>=0).astype(int) + (subset[j2]>=0).astype(int))[:-2]
                    if len(np.nonzero(membership == 2)[0]) == 0: #merge
                        subset[j1][:-2] += (subset[j2][:-2] + 1)
                        subset[j1][-2:] += subset[j2][-2:]
                        subset[j1][-2] += connection_all[k][i][2]
                        subset = np.delete(subset, j2, 0)
                    else: # as like found == 1
                        subset[j1][indexB] = partBs[i]
                        subset[j1][-1] += 1
                        subset[j1][-2] += candidate[partBs[i].astype(int), 2] + connection_all[k][i][2]

                # if find no partA in the subset, create a new subset
                elif not found and k < 17:
                    row = -1 * np.ones(20)
                    row[indexA] = partAs[i]
                    row[indexB] = partBs[i]
                    row[-1] = 2
                    row[-2] = sum(candidate[connection_all[k][i,:2].astype(int), 2]) + connection_all[k][i][2]
                    subset = np.vstack([subset, row])

    # delete some rows of subset which has few parts occur
    deleteIdx = []
    for i in range(len(subset)):
        if subset[i][-1] < 4 or subset[i][-2]/subset[i][-1] < 0.4:
            deleteIdx.append(i)
    subset = np.delete(subset, deleteIdx, axis=0)

    ## Show human part keypoint

    # visualize
    colors = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0], [0, 255, 0], \
            [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], [0, 0, 255], [85, 0, 255], \
            [170, 0, 255], [255, 0, 255], [255, 0, 170], [255, 0, 85]]

    # cmap = matplotlib.cm.get_cmap('hsv')

    # canvas = cv.imread(test_image) # B,G,R order
    # print len(all_peaks)
    # for i in range(15):
    #     rgba = np.array(cmap(1 - i/18. - 1./36))
    #     rgba[0:3] *= 255
    #     for j in range(len(all_peaks[i])):
    #         cv.circle(canvas, all_peaks[i][1][0:2], 4, colors[i], thickness=-1)

    # to_plot = cv.addWeighted(oriImg, 0.3, canvas, 0.7, 0)
    # plt.imshow(to_plot[:,:,[2,1,0]])
    # fig = matplotlib.pyplot.gcf()
    # fig.set_size_inches(11, 11)
    # # visualize 2
    canvas = oriImg
    img_ori = canvas.copy()
    
    for n in range(len(subset)):
        for i in range(numofparts - 1):    
            index_head = subset[n][i]        
            # if -1 in index_head:
            #     continue
            x = int(candidate[index_head.astype(int),0])
            y = int(candidate[index_head.astype(int),1])
            coo = (x,y)
            cv2.circle(img_ori,coo,3,colors[n],thickness = 3,)
    img_ori = img_ori[:,:,(2,1,0)]
    plt.imshow(img_ori)
    plt.show()
def main(images_dir ,model_prefix= None,start_epoch = 5900):
    from modelCPMWeight import CPMModel_test
    #%matplotlib inline
    def imshow(x,y):
        fig = plt.gcf();fig.set_size_inches(8, 8);plt.title(x); plt.imshow(y);plt.show()


    def padimg(img,destsize):
        s = img.shape    
        if(s[0] > s[1]):
            img_d = cv2.resize(img,dsize = None,fx = 1.0 * destsize/s[0], fy = 1.0 * destsize/s[0])
            img_temp = np.ones(shape = (destsize,destsize,3),dtype=np.uint8) * 128
            sd = img_d.shape
            img_temp[0:sd[0],0:sd[1],0:sd[2]]=img_d
        else:
            img_d = cv2.resize(img,dsize = None,fx = 1.0 * destsize/s[1],fy = 1.0 * destsize/s[1])
            img_temp = np.ones(shape = (destsize,destsize,3),dtype=np.uint8) * 128 
            sd = img_d.shape
            img_temp[0:sd[0],0:sd[1],0:sd[2]]=img_d
        return img_temp
    def getHeatAndPAF(img_path,models):
        oriImg = cv2.imread(img_path) # B,G,R order
        oriImg = padimg(oriImg,max_img_shape[0])
        class DataBatch(object):
            def __init__(self, data, label, pad=0):
                self.data = [data]
                self.label = 0
                self.pad = pad
        def preprocess(x_):
            r = []
            for size in imgshape_bind:
                imgs_resize = cv2.resize(x_, (size[0], size[1]), interpolation=cv2.INTER_CUBIC)
                imgs_transpose = np.transpose(np.float32(imgs_resize[:,:,:]), (2,0,1))/256 - 0.5
                imgs_batch = DataBatch(mx.nd.array([imgs_transpose[:,:,:]]), 0)
                r.append(imgs_batch)
            return r
        def suffix_heatmap(heatmap,size):
            heatmap = np.moveaxis(heatmap.asnumpy()[0], 0, -1)
            heatmap = cv2.resize(heatmap, (size[0], size[1]), interpolation=cv2.INTER_CUBIC)            
            return heatmap
        def suffix_paf(paf,size):
            paf = np.moveaxis(paf.asnumpy()[0], 0, -1)
            paf = cv2.resize(paf, (size[0], size[1]), interpolation=cv2.INTER_CUBIC)
            return paf
        
        def _getHeatPAF(args):
            onedata,model = args
            model.forward(onedata)
            result = model.get_outputs()
            max_shape = (oriImg.shape[0],oriImg.shape[1])
            heatmap = suffix_heatmap(result[1],max_shape)
            paf =     suffix_paf(    result[0],max_shape)
            return (heatmap,paf)
    
        imgs = preprocess(oriImg)
        results = _getHeatPAF((imgs[0],models[0]))
        heatmap_avg,paf_avg = results
    
        return img_path,oriImg,heatmap_avg,paf_avg
    def getModel(prefix,epoch,gpus = [0]):
        print(prefix)
        sym  = CPMModel_test(False)

        # mx.viz.plot_network(sym,shape = {"data":(1,3,368,368)}).view()
        batch_size = 1
        sym_load, newargs,aux_args = mx.model.load_checkpoint(prefix, epoch)
        print(set(sym.list_arguments()) - set(sym_load.list_arguments()))
        print(set(sym.list_arguments()) - set(newargs.keys()))

        # mx.viz.plot_network(sym_load,title = "sym_load").view()

        model = mx.mod.Module(symbol=sym, context=[mx.gpu(x) for x in gpus],                        
                              label_names=None)
        model.bind(data_shapes=[('data', (batch_size, 3, max_img_shape[0], max_img_shape[1]))],for_training = True)
        model.init_params(arg_params=newargs, aux_params=aux_args, allow_missing=False,allow_extra=False)
        return model
    cmodel = getModel(model_prefix,start_epoch)
    # for x,y,z in os.walk("/data1/yks/dataset/ai_challenger/ai_challenger_keypoint_validation_20170911/keypoint_validation_images_20170911"):
    for x,_,z in os.walk(images_dir):
        for name in z:
            img_path = os.path.join(x,name)
            img_path,oriImg,heatmap_avg,paf_avg = getHeatAndPAF(img_path,[cmodel])
            parse_heatpaf(oriImg,heatmap_avg,paf_avg)      
def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description='Demo Images ')
    parser.add_argument('--images', help='Images path', type=str)
    parser.add_argument('--prefix', help='model prefix', type=str)
    parser.add_argument('--epoch', help='model epoch', type=int)
    args = parser.parse_args()
    return args
if __name__ == "__main__":
    args = parse_args()
    main(args.images,args.prefix,args.epoch)
