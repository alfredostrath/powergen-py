# -*- coding: utf-8 -*-
"""

    Customer Clustering
    
    "Energy For Development" VIP (University of Strathclyde)
    
    Code by Alfredo Scalera (alfredo.scalera.2019@uni.strath.ac.uk)
    
"""

import math

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

import customer_cluster as cc


class CustomerClustering:
    
    def __init__(self, init_cluster, max_connections, network_voltage,
                 pole_cost, pole_spacing, resistance_per_km, current_rating,
                 cost_per_km, max_voltage_drop=None, max_distance=None):
        """
        Clusters customers together in preparation for network design.

        Parameters
        ----------
        init_cluster : InitCluster
            InitCluster object which initially pools all customers together.
        max_connections : int
            Maximum customers allowed per cluster.
        network_voltage : float
            Voltage at which network operates.
        pole_cost : TYPE
            Cost of electrical pole which will be placed at centroid
            location of cluster and to support line.
        pole_spacing : flaot
            Space between each electrical pole in meters.
        resistance_per_km : float
            Resistance per kilometer of cable used in ohm/km.
        current_rating : float
            Cable's max current rating.
        cost_per_km : float
            Cable's cost per kilometer.
        max_voltage_drop : float, optional
            Maximum voltage drop allowed between pole and customer.
            If None then maximum voltage drop is dictated by voltage
            regulation.
            The default is None.
        max_distance : float, optional
            Maximum distance allowed between pole and customer
            in meters.
            The default is None.

        """
        
        # network parameters
        self.network_voltage = network_voltage
        if max_voltage_drop == None:
            # if none specified, take as 6% of network voltage
            self.max_voltage_drop = 0.06 * network_voltage
        else:
            self.max_voltage_drop = max_voltage_drop
        
        # pole parameters
        self.max_distance = max_distance
        self.max_connections = max_connections
        self.pole_cost = pole_cost
        self.pole_spacing = pole_spacing
        
        # cable parameters
        self.res_m = resistance_per_km / 1000
        self.current_rating = current_rating
        self.cost_m = cost_per_km / 1000
        
        # initialise clusters array
        self.clusters = [init_cluster]
        
        self.all_clusters_valid = False
        
    @classmethod
    def import_from_csv(cls, filename, max_connections, network_voltage, 
                        pole_cost, pole_spacing, resistance_per_km, 
                        current_rating, cost_per_km, scale_factor=1,
                        max_voltage_drop=None, max_distance=None):
        """
        Creates CustomerCLustering object and generates Customer
        objects based on data within specified CSV file.

        Parameters
        ----------
        cls : TYPE
            DESCRIPTION.
        filename : string
            Name of CSV file containing customer information.
            Must follow default format.
        max_connections : int
            Maximum customers allowed per cluster.
        network_voltage : float
            Voltage at which network operates.
        pole_cost : TYPE
            Cost of electrical pole which will be placed at centroid
            location of cluster and to support line.
        pole_spacing : flaot
            Space between each electrical pole in meters.
        resistance_per_km : float
            Resistance per kilometer of cable used in ohm/km.
        current_rating : float
            Cable's max current rating.
        cost_per_km : float
            Cable's cost per kilometer.
        max_voltage_drop : float, optional
            Maximum voltage drop allowed between pole and customer.
            If None then maximum voltage drop is dictated by voltage
            regulation.
            The default is None.
        max_distance : float, optional
            Maximum distance allowed between pole and customer
            in meters.
            The default is None.

        Returns
        -------
        CustomerClustering
            CustoemrClustering object is returned with given parameters.

        """
        # read csv file as pandas dataframe
        df = pd.read_csv(str(filename))
        df = df.set_index("ID")
        
        # import customers and create initial single cluster
        customers = []
        for customer_id,data in df.iteritems():
            position = (scale_factor*data[0], scale_factor*data[1])  # X 0, Y 1
            power_demand = data[2:]
            customers.append(cc.Customer(customer_id,position,power_demand))
        
        init_cluster = cc.InitCluster(customers)
        
        return cls(init_cluster, max_connections, network_voltage, pole_cost,
                   pole_spacing, resistance_per_km, current_rating,
                   cost_per_km, max_voltage_drop=max_voltage_drop,
                   max_distance=max_distance)
    
    @classmethod
    def import_from_OTHER(cls):
        
        # PLACEHOLDER
        pass
    
    def cluster(self):
        """
        Clusters customers together given maximum connections, maximum
        voltage drop and maximum distance established when initialised.

        """
        
        while self.all_clusters_valid == False:
            
            # test constraints on all clusters
            self._test_constraints_all()  # updates value of all_clusters_valid
            
            # keep valid and apply kmeans (k=2) to invalid clusters
            new_clusters = []
            for cluster in self.clusters:
                if cluster.valid == True:  # keep valid clusters
                    new_clusters.append(cluster)
                elif cluster.valid == False:
                    # apply kmean to invalid cluster and add new ones
                    new_clusters += self._apply_kmeans(cluster)
            
            self.clusters = new_clusters
        
        #!!!
        self._merge_loop()
        
        self._total_cost()
    
    def _total_cost(self):
        """
        Calculates the total cost of the clustering setup.

        """
        
        d = np.array([cluster.distances for cluster in self.clusters],dtype=object)
        # concatenating all arrays and summing all elements
        self.total_distance = np.sum(np.concatenate(d))
        
        line_cost = self.total_distance * self.cost_m
        num_poles = math.ceil(self.total_distance / self.pole_spacing)
        num_poles += len(self.clusters)
        poles_cost = num_poles * self.pole_cost
        
        self.total_cost = line_cost + poles_cost
    
    def _test_constraints_all(self):
        """
        Tests constraints on all clusters.

        """
        
        self.all_clusters_valid = True  # assume all clusters valid initially
        
        for cluster in self.clusters:
            
            cluster.valid = True  # assume cluster valid initially
            
            # test constraints - these methods update cluster.valid
            if self.max_distance != None:  # if max distance specified
                cluster.test_distances()
            cluster.test_voltages(self.network_voltage,self.max_voltage_drop,
                                  self.res_m)
            cluster.test_max_connections(self.max_connections)
            
            if cluster.valid == False:
                self.all_clusters_valid = False
                
    def _apply_kmeans(self,cluster):
        """
        Splits cluster into two new clusters by applying kmeans with
        k = 2 (two clusters). 

        Parameters
        ----------
        cluster : Cluster
            Cluster object to be split.

        Returns
        -------
        new_clusters : list
            List containing two new cluster objects.

        """
        
        pos = np.array([customer.position for customer in cluster.customers])
        
        # apply kmeans to invalid clusters (k = 2)
        kmeans = KMeans(n_clusters=2).fit(pos)
        
        cluster_centers = kmeans.cluster_centers_
        cust_labels = kmeans.labels_
        new_clusters = []
        
        for ce_label, center in enumerate(cluster_centers):
            customers = []
            for cu_idx, customer in enumerate(cluster.customers):
                # if customer label = centroid label
                if cust_labels[cu_idx] == ce_label:
                    customers.append(customer)
            
            # create new cluster
            new_clusters.append(cc.Cluster(center,customers))
            
        return new_clusters
    
    def _merge_loop(self):
        """
        Attempts merging clusters together in order to reduce number
        of clusters.

        """
        
        print("\nAttempting merge")
        
        self._dist_matrix = self._init_dist_matrix()
        
        further_imp = True
        while further_imp:
            
            # find indices of closest pair
            idx_1, idx_2 = np.unravel_index(self._dist_matrix.argmin(),
                                            self._dist_matrix.shape)
            
            cluster_1 = self.clusters[idx_1]
            cluster_2 = self.clusters[idx_2]
            customers = cluster_1.customers + cluster_2.customers
            
            new_cluster = cc.InitCluster(customers)
            self._test_constraints(new_cluster)
            
            if new_cluster.valid == True:
                # remove old clusters and add new one
                self.clusters.remove(cluster_1)
                self.clusters.remove(cluster_2)
                self.clustere.append(new_cluster)
                
                # create new distance matrix
                self._dist_matrix = self._init_dist_matrix()
            
            elif new_cluster.valid == False:
                self._dist_matrix[idx_1,idx_2] = np.inf
                self._dist_matrix[idx_2,idx_1] = np.inf
            
            if np.isinf(self._dist_matrix).all():
                further_imp = False
            
        print("\nFinished merge attempt")

    def _test_constraints(self,cluster):
        """
        Tests maximum distance (if specified), maximum voltage and
        maximum customers constraints on cluster.

        Parameters
        ----------
        cluster : Cluster
            Cluster object on which constraints tested.

        """
        
        for cluster in self.clusters:
            
            cluster.valid = True  # assume cluster valid initially
            
            # test constraints - these methods update cluster.valid
            if self.max_distance != None:  # if max distance specified
                cluster.test_distances()
            cluster.test_voltages(self.network_voltage,self.max_voltage_drop,
                                  self.res_m)
            cluster.test_max_connections(self.max_connections)
    
    def _init_dist_matrix(self):
        """
        Creates distance matrix containing distances between clusters.
        Used for merging process. Pairs to i

        Returns
        -------
        dist_matrix : Numpy array
            Matrix containing distances between clusters.

        """
        # create distance matrix (distances between clusters)
        # used for merging process
        # pairs to ignore marked with inf
        
        size = (len(self.clusters),len(self.clusters))
        dist_matrix = np.full(size, np.inf)  # all values initially NaN
        for idx_1, cluster_1 in enumerate(self.clusters):
            
            print("\nchecking cluster",idx_1)
            
            # skip cluster if it already has maximum number of customers
            if cluster_1.n_customers == self.max_connections:
                
                print("\nskipped cluster",idx_1)
                
                continue
            
            # position of first cluster
            X_1 = cluster_1.position[0]
            Y_1 = cluster_1.position[1]
            
            for idx_2, cluster_2 in enumerate(self.clusters):
                
                if idx_1 == idx_2:
                    
                    print("\nsame clusters:",idx_1,idx_2)
                    
                    continue
                
                elif (cluster_1.n_customers + cluster_2.n_customers) > self.max_connections:
                    
                    print("\nmax customers",idx_1,idx_2)
                    
                    continue
                
                # position of second cluster
                X_2 = cluster_2.position[0]
                Y_2 = cluster_2.position[1]
                
                # euclidian distance between nodes
                dist = ((X_2 - X_1)**2 + (Y_2 - Y_1)**2)**(1/2)
                
                if self.max_distance != None and dist > self.max_distance:
                    
                    print("\ntoo distant",idx_1,idx_2)
                    
                    continue
                
                else:
                    dist_matrix[idx_1,idx_2] = dist
        
        return dist_matrix