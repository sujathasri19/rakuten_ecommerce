import glob
from sklearn.preprocessing import StandardScaler
import math
import re
import numpy as np
import rpy2.robjects
from rpy2.robjects.packages import importr
import rpy2.robjects.numpy2ri
rpy2.robjects.numpy2ri.activate()
base = importr('base')
stats = importr('stats')
lme4 = importr('lme4')
MuMIn = importr('MuMIn')

item_id_index_dic = {}
index_item_id_dic = {}

data_li = []
target_li = []


POS_LI= ['動名詞','形容名詞','名詞形態指示詞','普通名詞','格助詞','名詞接頭辞','名詞性名詞接尾辞','カタカナ','句点','形容詞',
      '連体詞','副詞','判定詞','助動詞', '接続詞', '指示詞', '連体詞形態指示詞', '副詞形態指示詞', '感動詞', '名詞', '副詞的名詞',
      '形式名詞', '固有名詞', '組織名', '地名' ,'人名', 'サ変名詞', '数詞', '時相名詞', '動詞', '助詞','副助詞','接続助詞',
      '終助詞', '接頭辞', '動詞接頭辞', 'イ形容詞接頭辞', 'ナ形容詞接頭辞', '接尾辞', '名詞性述語接尾辞', '名詞性名詞助数辞',
      '名詞性特殊接尾辞', '形容詞性述語接尾辞', '形容詞性名詞接尾辞', '動詞性接尾辞', '特殊', '読点', '括弧始', '括弧終','記号','空白',
      '未定義語', 'アルファベット', 'その他', '複合名詞', '複合形容詞']


BP_KEYWORD_LI = [] #keyword selected by BP


def read_desc(fin_desc_pro_pattern, fin_desc_head, fin_target_id):
    """read description files (both morph and description file and read target item id for evaluation"""
    # odd ratio add
    item_id_index_dic = {}
    index_item_id_dic = {}
    data_li = []
    item_count = 0

    print('# of pos in list:', len(POS_LI))
    print('# of bp keywords', len(BP_KEYWORD_LI))

    fin_li = glob.glob(fin_desc_pro_pattern)
    print(len(fin_li))

    target_id_set = set()
    target_id_cate_dic = {}

    if fin_target_id != None:
        print(fin_target_id)
        # for items with multiple ids
        for line in open(fin_target_id):
            target_cate, target_id, _ = line.strip().split('\t')
            target_id_set.add(target_id)
            target_id_cate_dic[target_id] = target_cate

    print('# of items in data', len(target_id_set))

    for fin in fin_li:
        item_id = fin.split('.')[2]

        if item_id not in target_id_set:
            # process item_id in the list only
            continue

        shop_id = item_id.split(':')[0]
        item_id_index_dic[item_id] = item_count
        index_item_id_dic[item_count] = item_id

        try:
            product_id = target_id_cate_dic[item_id]
        except KeyError:
            product_id = 'N'
            # for all data processing

        item_count += 1
        fea_dic = {}
        fea_dic['shop_id'] = shop_id
        fea_dic['product_id'] = product_id

        item_desc = [line.strip().split('\t')[3] for line in open(fin_desc_head + item_id, 'r')][0]

        for bp_keyword in BP_KEYWORD_LI:
            if bp_keyword[0] == '▁':
                # print(bp_keyword)
                bp_keyword_tmp = bp_keyword.replace('▁', ' ')

            else:
                bp_keyword_tmp = bp_keyword
            if bp_keyword_tmp in item_desc:
                bp_fea_name = 'bp.%s' % (bp_keyword)
                fea_dic.setdefault(bp_fea_name, 0)
                fea_dic[bp_fea_name] = 1

        # pos fea creation:
        tmp_pos_dic = {}

        for line in open(fin):
            if line == 'EOS\n':
                # ignore EOS
                continue

            line_items = line.strip().split('\t')
            word, origin, pos = line_items[0], line_items[1], line_items[2]
            origin = origin.replace(' ', '')

            if pos in POS_LI:
                pos_fea_name = 'pos.%s' % (pos)
                tmp_pos_dic.setdefault(pos_fea_name, 0)
                tmp_pos_dic[pos_fea_name] += 1
                fea_dic.setdefault('keyword', 0)
                fea_dic['keyword'] += 1
            else:
                # print(pos)
                pass


        tmp_test = 0
        for pos_name, pos_count in tmp_pos_dic.items():
            # to makte ratio of pos

            fea_dic.setdefault(pos_name, 0)
            fea_dic[pos_name] = pos_count

            pos_ratio_name = pos_name + '.r'
            fea_dic.setdefault(pos_ratio_name, 0)
            fea_dic[pos_ratio_name] = pos_count / fea_dic['keyword']

            tmp_test += pos_count / fea_dic['keyword']

        data_li.append(fea_dic)

    return (item_id_index_dic, index_item_id_dic, data_li)

def read_sales(index_item_id_dic, data_li, fin_sales, fin_desc_pattern):

    """read sales file create target . note that 0 sales ->0, 1 sales = log(1.5)"""
    target_li = [0] * len(data_li)

    sales_dic = {}
    fin_li = glob.glob(fin_desc_pattern)
    print('# of files for price:', len(fin_li))

    for fin in fin_li:
        for line in open(fin):
            line_items = line.strip().split('\t')
            item_id = line_items[1]
            try:
                item_price = int(line_items[2])
            except ValueError:
                print(fin)
                print(line)
                item_price = 0
            sales_dic.setdefault(item_id, [0, 0])
            sales_dic[item_id][0] = int(item_price)

    print('# of price info', len(sales_dic))

    for line in open(fin_sales):
        # angers:10041585 500     412     206000
        # combined sales
        # can be replaced with log sale info

        line_items = line.strip().split('\t')
        item_id = line_items[0]
        if item_id == 'item_id':
            # file with header
            continue

        unit_sales = line_items[2]

        try:
            sales_dic[item_id][1] = int(unit_sales)
        except KeyError:

            print('something is wrong.item_id not in desc appeared in sales',item_id)
            exit(1)

    for item_id, sales_info in sales_dic.items():
        try:
            item_id_index = item_id_index_dic[item_id]
        except KeyError:

            # this item is not in evaluation set
            continue

        data_li[item_id_index]['price'] = sales_info[0]
        data_li[item_id_index]['unit'] = sales_info[1]

        if sales_info[1] == 0:
            sales_info[1] = 0.0001
        try:
            target_li[item_id_index] = math.log(sales_info[1], 10)
        except ValueError:
            print(item_id_index,sales_info[1])

    return (target_li)


def fea_vetorizer_manual(data_li):
    categorical_fea_set = {'shop_id', 'product_id', 'unit'}
    bp_fea_li = ['bp.%s' % (x) for x in BP_KEYWORD_LI]
    categorical_fea_set.update(set(bp_fea_li))

    # print(len(categorical_fea_set))
    fea_li = ['keyword', 'price']

    fea_li.extend(['pos.%s' % (x) for x in POS_LI])
    fea_li.extend(['pos.%s.r' % (x) for x in POS_LI])

    converted_data_index = dict(zip(fea_li, range(0, len(fea_li))))
    # print(converted_data_index)
    converted_data_li = []

    tmp_li = [0.0] * len(fea_li)

    for item_fea_dic in data_li:
        # print(item_fea_dic)
        for k, v in item_fea_dic.items():
            if k in categorical_fea_set:
                pass
            else:
                tmp_li[converted_data_index[k]] = v
        converted_data_li.append(tmp_li)
        tmp_li = [0.0] * len(fea_li)

    scaled_data = StandardScaler().fit(converted_data_li).transform(converted_data_li)

    fea_li.extend(bp_fea_li)

    fea_li.append('shop_id')
    fea_li.append('product_id')
    print('# of total feature', len(fea_li))

    converted_data_li = []
    for i in range(0, len(scaled_data)):
        # deal with categorical values
        tmp_li = list(scaled_data[i])

        # odd keywords ratio
        tmp_bp_ratio_li = []
        for bp_key in bp_fea_li:
            try:
                tmp_bp_ratio_li.append(data_li[i][bp_key])
            except KeyError:
                tmp_bp_ratio_li.append(0)

        tmp_li.extend(tmp_bp_ratio_li)


        shop_id = data_li[i]['shop_id']
        cate = data_li[i]['product_id']
        tmp_li.append(shop_id)
        tmp_li.append(cate)

        converted_data_li.append(tmp_li)

    # print(len(tmp_li))
    # print(converted_data_li[0])
    return (converted_data_li, fea_li)

def convert_to_rdata(scaled_data, fea_li, target_li):

    # conver data for R
    r_input = np.concatenate((np.array(scaled_data), np.array(target_li).reshape(450, 1)), axis=1)
    r_feature = fea_li[:]
    r_feature.append('target')
    r_input_t = r_input.T
    r_df = {}
    for i in range(0, len(r_feature)):
        # print(r_feature[i])
        fea_name = r_feature[i]
        if fea_name == 'shop_id' or fea_name == 'product_id':
            r_df[fea_name] = rpy2.robjects.FactorVector(r_input_t[i])

        else:
            r_df[fea_name] = rpy2.robjects.vectors.FloatVector(r_input_t[i])

    dataf = rpy2.robjects.DataFrame(r_df)

    return(dataf)


if __name__ == '__main__':

    WORKING_DIR='/Users/forumai/Documents/work/stanford_work/item_id_desc/sales_regression/'
    fin_desc_pro_pattern = '/Users/forumai/Documents/work/stanford_work/item_id_desc/choco_desc_pro/choco.desc.*.pre'
    fin_desc_pattern = '/Users/forumai/Documents/work/stanford_work/item_id_desc/choco_desc/choco.desc.*[0-9]'

    fin_desc_head = '/Users/forumai/Documents/work/stanford_work/item_id_desc/choco_desc/choco.desc.'
    fin_sales = '/Users/forumai/Documents/work/stanford_work/item_id_desc/sales_regression/choco_all.sales2.combined.txt'
    multiple_item_id = '/Users/forumai/Documents/work/stanford_work/item_id_desc/choco_multi_candid3.txt'

    fin_bp_keyword =  '/Users/forumai/Documents/work/stanford_work/GENERATED_WORDS/BPE/rnn_states-bahdanau-reverse_TRUE-after_split-wv_size_16/choco-best-rnn_states-bahdanau-reverse_TRUE-after_split-wv_size_16'

    NUM_OF_TOP_KEYWORD = 300
    BP_KEYWORD_LI = [line.strip().split()[0] for line in open(fin_bp_keyword) if len(line.strip().split()[0]) > 1][:NUM_OF_TOP_KEYWORD]

    item_id_index_dic, index_item_id_dic, data_li = read_desc(fin_desc_pro_pattern, fin_desc_head, multiple_item_id)
    target_li = read_sales(index_item_id_dic, data_li, fin_sales, fin_desc_pattern)
    scaled_data, feature_name = fea_vetorizer_manual(data_li) # data for scikit

    #print(feature_name)

    #start R code
    dataf = convert_to_rdata(scaled_data, feature_name, target_li)
    rpy2.robjects.globalenv['dataset'] = dataf #append dataframe to environment
    pos_index = rpy2.robjects.r('''grep("^pos", colnames(dataset))''')
    bp_index = rpy2.robjects.r('''grep("^bp", colnames(dataset))''')

    pos_index_neg = rpy2.robjects.IntVector(tuple([x*-1 for x in pos_index]))
    bp_index_neg = rpy2.robjects.IntVector(tuple([x*-1 for x in bp_index]))


    # selection from df

    rpy2.robjects.globalenv['dataset_wo_pos'] = dataf.rx(True, pos_index_neg)
    rpy2.robjects.globalenv['dataset_wo_bp'] = dataf.rx(True, bp_index_neg)

    #print(rpy2.robjects.r('''colnames(dataset_wo_pos)'''))
    #print(rpy2.robjects.r('''colnames(dataset_wo_bp)'''))
    #print(rpy2.robjects.r('''colnames(dataset)'''))

    #contain all features w/o product_id. i.e. containing shop and price for usual regression
    #this is because regular regression R^2 is to see whether all features can explain sales well

    #all


    result = rpy2.robjects.r('''fit=lmer(target ~ . -price + -shop_id -product_id  + (1|shop_id) + (1|product_id), data=dataset)''')
    rpy2.robjects.globalenv['lm_result'] = result
    all_result = list(rpy2.robjects.r('''r.squaredGLMM(lm_result)'''))#language only vs # language/shop/product_id

    result = rpy2.robjects.r('''fit=lm(target ~ . -product_id, data=dataset)''')
    all_result.append(float(base.summary(result)[8][0]))


    #all - #of keyword
    result = rpy2.robjects.r('''fit=lmer(target ~ . -keyword -price + -shop_id -product_id  + (1|shop_id) + (1|product_id), data=dataset)''')
    rpy2.robjects.globalenv['lm_result'] = result
    result_wo_keyword = list(rpy2.robjects.r('''r.squaredGLMM(lm_result)''')) #language only vs # language/shop/product_id


    result = rpy2.robjects.r('''fit=lm(target ~ . -keyword -product_id, data=dataset)''')
    result_wo_keyword.append(float(base.summary(result)[8][0]))  # adjusted_r



    #all - pos
    result = rpy2.robjects.r('''fit=lmer(target ~ . -price + -shop_id -product_id  + (1|shop_id) + (1|product_id), data=dataset_wo_pos)''')
    rpy2.robjects.globalenv['lm_result'] = result
    result_wo_pos = list(rpy2.robjects.r('''r.squaredGLMM(lm_result)''')) #language only vs # language/shop/product_id

    result = rpy2.robjects.r('''fit=lm(target ~ . -product_id, data=dataset_wo_pos)''')
    result_wo_pos.append(float(base.summary(result)[8][0]))  # adjusted_r



    #all - pos  -keyword
    # result = rpy2.robjects.r('''fit=lmer(target ~ . -price + -shop_id -product_id -keyword + (1|shop_id) + (1|product_id), data=dataset_wo_pos)''')
    # rpy2.robjects.globalenv['lm_result'] = result
    # result_wo_pos = rpy2.robjects.r('''r.squaredGLMM(lm_result)''') #language only vs # language/shop/product_id
    #
    # result = rpy2.robjects.r('''fit=lm(target ~ . -keyword -product_id, data=dataset_wo_pos)''')
    # result_wo_pos = base.summary(result)[8]  # adjusted_r

    #all - bp

    # all - pos
    result = rpy2.robjects.r(
        '''fit=lmer(target ~ . -price + -shop_id -product_id  + (1|shop_id) + (1|product_id), data=dataset_wo_bp)''')
    rpy2.robjects.globalenv['lm_result'] = result
    result_wo_bp = list(rpy2.robjects.r('''r.squaredGLMM(lm_result)'''))  # language only vs # language/shop/product_id

    result = rpy2.robjects.r('''fit=lm(target ~ . -product_id, data=dataset_wo_bp)''')
    result_wo_bp.append(float(base.summary(result)[8][0]))  # adjusted_r

    print('result\tfix_r2\trandom_effect_r2\t\tadjusted')
    print('all\t\t%.4f%.4f\t\t%.4f' % (all_result[0], all_result[1], all_result[2]))
    print('-# of keyword\t%.4f\t%.4f\t\t%.4f' % (result_wo_keyword[0], result_wo_keyword[1], result_wo_keyword[2]))
    print('-pos\t%.4f\t%.4f\t\t%.4f' % (result_wo_pos[0], result_wo_pos[1], result_wo_pos[2]))
    print('-bp\t%.4f\t%.4f\t\t%.4f' % (result_wo_bp[0], result_wo_bp[1], result_wo_bp[2]))