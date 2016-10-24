'''flatDWT
Created: September 29, 2016

This script must be able to detect if a flat is acceptable inmediatly after 
exposure
Use dflats tagged as bad in FLAT_QA 
Use cropped pieces of code from flatStat and decam_test

Oct 4th: DMWY as selected wavelet (symmetric,orthogonal,biorthogonal)

STEPS:
1) Do it on a single ccd with all the possibilities --done
2) do it well on FP with all the possibilities
3) Do it for good/bad flats and compare results
'''
import os
import sys
import time 
import numpy as np
import scipy.stats
import scipy.signal
import matplotlib.pyplot as plt
import fitsio
import pywt
import tables

class Toolbox():
    '''methods to be inserted in other 
    '''
    @classmethod
    def detect_outlier(cls,imlayer):
        ''' Estimate Iglewicz and Hoaglin criteria for outlier 
        AND REPLACE BY MEDIAN OF VICINITY! Change this because we only
        want the values masked, not to replace them
        http://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm
        Formula:
        Z=0.6745(x_i - median(x)) / MAD
        if abs(z) > 3.5, x_i is a potential outlier
        Boris Iglewicz and David Hoaglin (1993), "Volume 16: How to Detect and 
        Handle Outliers", The ASQC Basic References in Quality Control: 
        Statistical Techniques, Edward F. Mykytka, Ph.D., Editor.
        '''
        from statsmodels.robust import scale #for mad calculation
        from scipy.stats import norm
        '''Percent point function (inverse of cdf -- percentiles) of a normal
        continous random variable
        '''
        cte = norm.ppf(0.75) #aprox 0.6745
        '''Flatten the image, to estimate median
        '''
        flat_im = imlayer.ravel()
        #flat_im=flat_im[flat_im!=-1]#exclude '-1' values
        MAD = np.median( np.abs( flat_im-np.median(flat_im) ) )
        #alternative: scale.mad(flat_im, c=1, axis=0, center=np.median)
        Zscore = cte*(flat_im-np.median(flat_im))/MAD
        Zscore = np.abs(Zscore)
        ''' search for outliers and if present replace by the 
        median of neighbors
        '''
        if len(Zscore[Zscore>3.5])>0:
            for k in range(0,imlayer.shape[0]):
                for m in range(0,imlayer.shape[1]):
                    if np.abs( cte*(imlayer[k,m]-np.median(flat_im))/MAD )>3.5:
                        imlayer[k,m] = np.nan
            return imlayer
        else:
            return imlayer

    @classmethod
    def quick_stat(cls,arr_like):
        MAD = np.median( np.abs(arr_like-np.median(arr_like)) )
        print '__________'
        print '* Min | Max | Mean = {0} | {1} | {2}'.format(
            np.min(arr_like),np.max(arr_like),np.mean(arr_like))
        print '* Median | Std | MAD = {0} | {1} | {2}'.format(
            np.median(arr_like),np.std(arr_like),MAD)
        print '* .25 | .5 | .75 = {0} | {1} | {2}'.format(
            np.percentile(arr_like,.25),np.percentile(arr_like,.5),
            np.percentile(arr_like,.75))
        return False

    @classmethod
    def view_dwt(cls,img_arr):
        '''Display all the availbale DWT (single level) for the input array  
        '''
        t1 = time.time()
        count = 0
        for fam in pywt.families():
            for mothwv in pywt.wavelist(fam):
                for mod in pywt.Modes.modes:
                    print '\tWavelet: {0} / Mode: {1}'.format(mothwv,mod)
                    (c_A,(c_H,c_V,c_D)) = pywt.dwt2(img_arr,
                                                    pywt.Wavelet(mothwv),
                                                    mod)
                    count += 1 
                    fig=plt.figure(figsize=(6,11))
                    ax1=fig.add_subplot(221)
                    ax2=fig.add_subplot(222)
                    ax3=fig.add_subplot(223)
                    ax4=fig.add_subplot(224)
                    ax1.imshow(c_A,cmap='seismic')#'flag'
                    ax2.imshow(c_V,cmap='seismic')
                    ax3.imshow(c_H,cmap='seismic')
                    ax4.imshow(c_D,cmap='seismic')
                    plt.title('Wavelet: {0} / Mode: {1}'.format(mothwv,mod))
                    plt.subplots_adjust(left=.06, bottom=0.05,
                                        right=0.99, top=0.99,
                                        wspace=0., hspace=0.)
                    plt.show()
        t2 = time.time()
        print ('\nTotal time in all {1} modes+mother wavelets: {0:.2f}\''
               .format((t2-t1)/60.,count))

    @classmethod
    def range_str(cls,head_rng):
        head_rng = head_rng.strip('[').strip(']').replace(':',',').split(',')
        return map(lambda x: int(x)-1, head_rng)


class FPSci():
    '''methods for loading science focal plane (1-62), inherited 
    from crosstalk
    Maybe import crosstalk
    '''
    def __init__(self,folder,parent_root):
        '''Simple method to construct the focal plane array 
        '''
        aux_fp = np.zeros((4096*8,2048*13),dtype=float)
        max_r,max_c = 0,0
        #list all on a directory having same root
        for (path,dirs,files) in os.walk(folder):
            for index,item in enumerate(files):   #file is a string
                if (parent_root in item):
                    M_header = fitsio.read_header(path+item)
                    M_hdu = fitsio.FITS(path+item)[0]
                    posA = Toolbox.range_str(M_header['detseca'])
                    posB = Toolbox.range_str(M_header['detsecb'])
                    datA = Toolbox.range_str(M_header['dataseca'])
                    datB = Toolbox.range_str(M_header['datasecb'])
                    if posA[1] > max_c: max_c = posA[1]
                    if posA[3] > max_r: max_r = posA[3]
                    if posB[1] > max_c: max_c = posB[1]
                    if posB[3] > max_r: max_r = posB[3]
                    ampA = M_hdu.read()[datA[2]:datA[3]+1,datA[0]:datA[1]+1]
                    ampB = M_hdu.read()[datB[2]:datB[3]+1,datB[0]:datB[1]+1]
                    aux_fp[posA[2]:posA[3]+1,posA[0]:posA[1]+1] = ampA
                    aux_fp[posB[2]:posB[3]+1,posB[0]:posB[1]+1] = ampB
        self.fpSci = aux_fp[:max_r+1,:max_c+1]
        aux_fp = None
    

class DWT():
    '''methods for discrete WT of one level
    pywt.threshold
    '''
    @classmethod
    def cutlevel(cls):
        return False
    
    @classmethod
    def single_level(cls,img_arr,wvfunction='dmey',wvmode='symmetric'):
        '''DISCRETE wavelet transform
        Wavelet families available: 'haar', 'db', 'sym', 'coif', 'bior', 
        'rbio','dmey'
        http://www.pybytes.com/pywavelets/regression/wavelet.html
        - When flat shows issues, it presents discontinuities in flux
        - To perform the wavelet, border effects must be considered
        - Bumps at the edge are by now flagged but if something
          could be done, it would represent a huge improvement, specially 
          for th SN team
        FOR THE ENTIRE FOCAL PLANE
        --------------------------
        Must fill the interCCD space with zeroes (?) or interpolation.
        Scales must define the refinement scales I will look. The more scales, 
        the slower calculation and better the resolution.
        - MODES: different ways to deal with border effects
        - DWT2/WAVEDEC2 output is a tuple (cA, (cH, cV, cD)) where (cH, cV, cD)
          repeats Nwv times
        Coeffs:
        c_A : approximation (mean of coeffs) coefs
        c_H,c_V,c_D : horizontal detail,vertical,and diagonal coeffs
        '''
        print type(img_arr)
        (c_A,(c_H,c_V,c_D)) = pywt.dwt2(img_arr,pywt.Wavelet(wvfunction),
                                        wvmode)
        #rec_img = pywt.idwt2((c_A,(c_H,c_V,c_D)),WVstr)#,mode='sym')
        '''reduced set of parameters through pywt.threshold()
        with args: soft, hard, greater, less
        To define a set of points (with same dimension as the image), the 
        detailed coeffs must be employed
        '''
        return c_A,c_H,c_V,c_D
        
    @classmethod
    def multi_level(cls,img_arr,wvfunction='dmey',wvmode='symmetric',Nlev=8):
        '''Wavelet Decomposition in multiple levels, opossed to DWT which is
        the wavelet transform of one level only
        - Nlev: number of level for WAVEDEC2 decomposition
        - WAVEDEC2 output is a tuple (cA, (cH, cV, cD)) where (cH, cV, cD)
          repeats Nwv times
        '''
        c_ml = pywt.wavedec2(img_arr,pywt.Wavelet(wvfunction),
                             wvmode,level=Nlev)
        aux_shape = []
        for i in range(len(c_ml)):
            if i == 0:
                aux_shape.append(c_ml[i].shape)
            else:
                aux_shape.append(c_ml[i][0].shape)
        cls.cmlshape = aux_shape
        return c_ml


class Coeff(DWT):
    '''method for save results of DWT on a compressed pytables
    '''
    @classmethod
    def set_table(cls,str_tname):
        print 'try 1 \t',DWT.cmlshape
        print 'try 2 \t',DWT().cmlshape
        
        class Levels(tables.IsDescription):
            c_A = tables.Float32Col(shape=DWT.cmlshape[0])
            c1 = tables.Float32Col(shape=DWT.cmlshape[1])
            c2 = tables.Float32Col(shape=DWT.cmlshape[2])
            c3 = tables.Float32Col(shape=DWT.cmlshape[3]) 
            c4 = tables.Float32Col(shape=DWT.cmlshape[4])
            c5 = tables.Float32Col(shape=DWT.cmlshape[5])
            c6 = tables.Float32Col(shape=DWT.cmlshape[6])
            c7 = tables.Float32Col(shape=DWT.cmlshape[7])
            c8 = tables.Float32Col(shape=DWT.cmlshape[8])
        cls.h5file = tables.open_file(str_tname,mode='w',
                                    title='DWT multilevel decomposition',
                                    driver='H5FD_CORE')
        #driver_core_backing_store=0)
        #coeff: group name, DWT coeff: brief description
        group = cls.h5file.create_group('/','coeff','DWT coeff')
        #FP: table name, FP wavelet decomposition:ttable title
        cls.cml_table = cls.h5file.create_table(group,'FP',Levels,'Wavedec')

    @classmethod
    def fill_table(cls,coeff_tuple):
        #fills multi-level DWT with N=8
        cml_row = Coeff.cml_table.row
        for m in range(3):
            cml_row['c_A'] = coeff_tuple[0]
            cml_row['c1'] = coeff_tuple[1][m]
            cml_row['c2'] = coeff_tuple[2][m]
            cml_row['c3'] = coeff_tuple[3][m]
            cml_row['c4'] = coeff_tuple[4][m]
            cml_row['c5'] = coeff_tuple[5][m]
            cml_row['c6'] = coeff_tuple[6][m]
            cml_row['c7'] = coeff_tuple[7][m]
            cml_row['c8'] = coeff_tuple[8][m]
            cml_row.append() 

    @classmethod
    def close_table(cls):
        Coeff.h5file.close()


if __name__=='__main__':
    path = '/Users/fco/Code/shipyard_DES/raw_201608_dflat/'

    #load crosstalk module ite returns a big 2D array
    whole_fp = FPSci(path,'DECam_00565285_').fpSci
    #desarchive/OPS/precal/20160811-r2440/p02/xtalked-dflat
    
    print '\tstarting DWT'
    t1 = time.time()
    c_A,c_H,c_V,c_D = DWT.single_level(whole_fp)
    print whole_fp
    t2 = time.time()
    print '\n\tElapsed time in DWT the focal plane: {0:.2f}\''.format((t2-t1)
                                                                    /60.)
    if True:
        print '\tstarting DWT multilevel'
        t1 = time.time()
        c_ml = DWT.multi_level(whole_fp,Nlev=8)
        t2 = time.time()
        print '\n\tElapsed time in DWT in 8 levels: {0:.2f}\''.format((t2-t1)
                                                                    /60.)
        #init table
        Coeff.set_table('dwt_ID.h5')
        #fill table
        Coeff.fill_table(c_ml)
        #close table
        Coeff.close_table()
    
    #exit()
    #auxFn = TestCCD()
    #header,img = auxFn.opentest(fname)
    #dwt_a = DWT()
    #dwt_a.single_level(img[:,:])
    #dwt_a.multi_level(img[:,:])
