#!/home/wangjing/Apps/python/bin/python
#!/usr/bin/env python
"""  Estimate the Null Model using Entropy Maximization
"""
from __future__ import print_function, division, absolute_import
import numpy as np
import openopt as opt
import matplotlib.pyplot as plt
import scipy.sparse as sps
from .Util import progress_bar
from .Util import load, dump

npv = [int(i) for i in np.__version__.rsplit('.')]

def QP(yp, c_vec, N, T, solver='cplex', H_vec=None, b_vec=None):
    # the shape of c_vec is  (N*N, T)
    a_vec = np.dot(c_vec, yp)

    hc = 1.0 / a_vec # scale coef for H
    hc[hc == np.inf] = 0

    hct = np.tile(np.sqrt(hc).reshape(-1, 1), (1, T))
    c_vec_scale = c_vec * hct
    H = np.einsum('ij,ik->jk', c_vec_scale, c_vec_scale)

    bc = np.log(a_vec) - 1
    bc[bc == -np.inf] = 0
    b = np.dot(bc, c_vec)

    print('finish calculating H, b')

    p = opt.QP(H=1 * H,
               f=1 * b,
               Aeq=np.ones((T,)),
               beq=1.0,
               lb=0.0 * np.zeros((T,)),
               ub=1.0 * np.ones((T,)))
    r = p._solve(solver, iprint=0)
    f_opt, x_opt = r.ff, r.xf
    # print('x_opt', x_opt)
    # print('f_opt', f_opt)
    return f_opt, x_opt

def test():
    yp = np.array([1.0, 0.0])
    c_vec = np.zeros((2.0, 2.0, 2.0))
    c_vec[0, 0, :] = [3.0, 1.0]
    c_vec[0, 1, :] = [2.0, 1.0]
    c_vec[1, 0, :] = [3.0, 4.0]
    c_vec[1, 1, :] = [3.0, 2.0]

    QP(yp, c_vec, 'cvxopt_qp')

#############


def EstTrafProb(adj_mats, eps=1e-5, T=None,):
    """  Estimate the probability distribution for Generalized Configuration
    Model (GCM)

    Parameters
    ---------------
    adj_mats : a list of np.2darray
        adj_matrs of some Social Interaction Graphs (SIGs)

    Returns
    --------------
    tr : dict
        solution : list
            weights of each graph
        f_opt : float
            the maximial entropy
        err : float
            error of two adjacent solution
    """

    if npv[1] < 7:
        raise Exception('to run EstTrafProb. numpy version must be greater than 1.7')


    if T is not None:
        adj_mats = adj_mats[:T]

    N = adj_mats[0].shape[0]  # size of the graph
    T = len(adj_mats)   # number of graphs
    # calculate C from degrees
    # k_in and k_out are NxT array
    k_in = np.vstack([mat.sum(axis=0) for mat in adj_mats]).T
    k_out = np.hstack([mat.sum(axis=1) for mat in adj_mats])
    m = np.array(k_in.sum(axis=0)).reshape(-1)  # m is 1xT array
    m2 = (m ** 2)
    c_vec = np.zeros((N * N, T))
    for t in xrange(T):
        mat = np.outer(k_out[:, t], k_in[:, t]) * 1.0 / m2[t]
        c_vec[:, t] = mat.reshape(-1)
    print('finish calculate c_vec')
    # yp = 1.0 / T * np.ones((T,))
    yp = np.random.rand(T)
    yp /= np.sum(yp)
    it_n = -1
    tr = dict()
    tr['err'] = []
    while it_n < 10:
        it_n += 1
        print('iteration: ', it_n)

        f_obj, y_new = QP(yp, c_vec, N, T, 'cplex')
        err = np.sum(np.abs(y_new - yp))
        print('err', err)
        tr['err'].append(err)
        if err < eps:
            break
        yp = y_new
    tr['solution'] = yp
    tr['f_obj'] = f_obj
    return tr


def ident_pivot_nodes(adjs, weights, thres):
    """ identify the pivot nodes

    Parameters
    ---------------
    adjs : a list of sparse matrices.
        SIG. Assume to be symmetric
    weights : a list of float
        weights of each SIG

    Returns
    --------------
    """
    N = adjs[0].shape[0]
    T = len(weights)
    total_inta_mat = np.zeros((N, T))
    for t, adj in enumerate(adjs):
        total_inta_mat[:, t] = adj.sum(axis=1).reshape(-1)
    total_inta_mat = np.dot(total_inta_mat, weights)
    total_inta_mat /= np.max(total_inta_mat)
    pivot_nodes, = np.where(total_inta_mat > thres)
    return pivot_nodes


def cal_inta_pnodes(adjs, weights, pivot_nodes):
    """  calculate the interactions of nodes with pivot_nodes using GCM

    Parameters
    ---------------
    adjs : a list of sparse matrices.
        SIG. Assume to be symmetric
    weights : a list of float
        weights of each SIG
    pivot_nodes : list of ints
        a set of nodes that may be leaders or the victims of the botnet

    Returns
    --------------
    """
    N = adjs[0].shape[0]
    T = len(weights)
    inta_mat = np.zeros((N, T))
    for t, adj in enumerate(adjs):
        res = np.sum(adj[list(pivot_nodes), :].todense(), axis=0).reshape(-1)
        inta_mat[:, t] = res
    inta = np.dot(inta_mat, weights)
    return inta

def cal_cor_graph(adjs, pivot_nodes, thres):
    """  calculate the correlation graph

    Parameters
    ---------------
    adjs : a list of sparse matrices.
        SIG. Assume to be symmetric
    pivot_nodes : list of ints
        a set of nodes that may be leaders or the victims of the botnet
    thres : float
        threshold for constructing correlation graph

    Returns
    --------------
    A : np.2darray
        adj matrix of the correlation graph
    npcor : np.2darray
        matrix of correlation coefficients.
    """
    inta = lambda x: np.sum(np.array(adj[pivot_nodes, :].todense()), axis=0).reshape(-1)
    traf = np.asarray([inta(adj) for adj in adjs])
    npcor = np.corrcoef(traf, rowvar=0)
    np_cor_no_nan = np.nan_to_num(npcor)
    A = np_cor_no_nan > thres
    return A, npcor


