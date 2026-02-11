# Guide Complet de Préparation - Stage Développeur Service Kubernetes

## Table des Matières
1. Kubernetes - Les Fondamentaux
2. Ingress Controller - Architecture et Fonctionnement
3. HELM - Package Manager pour Kubernetes
4. Conteneurisation avec Docker
5. Cloud Computing et AWS
6. DevOps et Observabilité
7. Sécurité et Réseaux
8. Le Contexte du Stage chez 3DS OUTSCALE

---

## 1. KUBERNETES - LES FONDAMENTAUX

### 1.1 Qu'est-ce que Kubernetes ?

Kubernetes (souvent abrégé K8s) est un système d'orchestration de conteneurs open-source développé initialement par Google. Son rôle principal est d'automatiser le déploiement, la mise à l'échelle et la gestion d'applications conteneurisées.

**Pourquoi Kubernetes existe-t-il ?**

Imaginez que vous ayez une application composée de plusieurs services (une base de données, une API, une interface web). Sans orchestrateur :
- Vous devez démarrer manuellement chaque conteneur
- Si un conteneur plante, personne ne le redémarre
- Distribuer la charge entre plusieurs instances est complexe
- Les mises à jour nécessitent des interruptions de service

Kubernetes résout tous ces problèmes en automatisant la gestion de vos conteneurs.

### 1.2 Architecture de Kubernetes

**Le Cluster Kubernetes**

Un cluster Kubernetes est composé de deux types de machines :

#### A. Le Control Plane (Plan de Contrôle)

C'est le "cerveau" du cluster. Il comprend plusieurs composants :

1. **kube-apiserver** : 
   - C'est le point d'entrée de toutes les commandes Kubernetes
   - Quand vous tapez `kubectl get pods`, c'est l'API server qui répond
   - Il valide et traite toutes les requêtes REST
   - Il est le seul composant qui communique directement avec etcd

2. **etcd** :
   - Base de données clé-valeur distribuée
   - Stocke TOUT l'état du cluster (configuration, secrets, services, pods...)
   - Si vous perdez etcd, vous perdez votre cluster
   - Utilise l'algorithme de consensus Raft pour maintenir la cohérence

3. **kube-scheduler** :
   - Décide sur quel nœud (node) placer chaque nouveau pod
   - Prend en compte : ressources disponibles (CPU, RAM), contraintes (affinités, taints/tolerations), localisation des données
   - Exemple : si votre pod demande 4GB de RAM, le scheduler ne le placera que sur un nœud ayant au moins 4GB disponibles

4. **kube-controller-manager** :
   - Exécute différents contrôleurs qui surveillent l'état du cluster
   - Contrôleur de réplication : s'assure que le bon nombre de pods tourne
   - Contrôleur de nœuds : détecte quand un nœud tombe
   - Contrôleur d'endpoints : peuple les objets Endpoints (lie Services et Pods)
   - Contrôleur de service accounts & tokens : crée des comptes par défaut

5. **cloud-controller-manager** (optionnel) :
   - Interface avec l'API du fournisseur cloud (AWS, Azure, GCP)
   - Gère les ressources cloud comme les load balancers, les volumes de stockage

#### B. Les Worker Nodes (Nœuds de Travail)

Ce sont les machines qui exécutent réellement vos applications. Chaque nœud contient :

1. **kubelet** :
   - "Agent" qui tourne sur chaque nœud
   - Communique avec l'API server
   - S'assure que les conteneurs décrits dans les PodSpecs tournent correctement
   - Rapporte l'état du nœud et des pods au control plane
   - Gère le cycle de vie des conteneurs via le container runtime

2. **kube-proxy** :
   - Maintient les règles réseau sur les nœuds
   - Permet la communication réseau vers vos pods
   - Implémente le concept de Service Kubernetes
   - Peut utiliser iptables, IPVS ou userspace pour router le trafic

3. **Container Runtime** :
   - Le logiciel responsable de l'exécution des conteneurs
   - Exemples : Docker, containerd, CRI-O
   - Kubernetes utilise l'interface CRI (Container Runtime Interface)

### 1.3 Les Objets Kubernetes Fondamentaux

#### A. Pod

**Définition** : Un Pod est la plus petite unité déployable dans Kubernetes. C'est un wrapper autour d'un ou plusieurs conteneurs.

**Caractéristiques** :
- Partage le même namespace réseau (IP address commune)
- Partage les mêmes volumes de stockage
- Conteneurs dans un pod peuvent communiquer via localhost
- Généralement, un Pod = un conteneur (pattern le plus courant)

**Exemple de YAML** :
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mon-app
  labels:
    app: frontend
spec:
  containers:
  - name: nginx
    image: nginx:1.21
    ports:
    - containerPort: 80
    resources:
      requests:
        memory: "64Mi"
        cpu: "250m"
      limits:
        memory: "128Mi"
        cpu: "500m"
```

**Cycle de vie d'un Pod** :
1. **Pending** : Pod accepté mais conteneurs pas encore créés
2. **Running** : Pod assigné à un nœud, au moins un conteneur tourne
3. **Succeeded** : Tous les conteneurs se sont terminés avec succès
4. **Failed** : Au moins un conteneur s'est terminé en erreur
5. **Unknown** : État du Pod ne peut être déterminé

**Points importants** :
- Les Pods sont éphémères (jetables)
- Quand un Pod meurt, il n'est PAS redémarré - un nouveau Pod est créé
- C'est pourquoi on ne crée jamais de Pods directement en production

#### B. ReplicaSet

**Définition** : Un ReplicaSet garantit qu'un nombre spécifié de répliques de pods tourne à tout moment.

**Fonctionnement** :
- Vous spécifiez un nombre désiré de répliques (ex: 3)
- Le ReplicaSet surveille continuellement
- Si un pod meurt → il en crée un nouveau
- Si trop de pods → il en supprime
- Si pas assez de pods → il en crée

**Exemple** :
```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: frontend-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
```

**Comment ça marche techniquement ?**

Le contrôleur ReplicaSet dans le kube-controller-manager :
1. Interroge l'API server toutes les X secondes
2. Compte les pods correspondant au selector
3. Compare avec le nombre désiré (spec.replicas)
4. Crée ou supprime des pods pour atteindre l'état désiré

**Label Selector** :
- C'est le mécanisme par lequel le ReplicaSet identifie "ses" pods
- Les labels sont des paires clé-valeur attachées aux objets
- Le selector utilise ces labels pour filtrer

**Note importante** : On ne crée presque jamais de ReplicaSet directement. On utilise des Deployments.

#### C. Deployment

**Définition** : Un Deployment est une abstraction de plus haut niveau qui gère des ReplicaSets et fournit des mises à jour déclaratives pour les Pods.

**Pourquoi utiliser un Deployment plutôt qu'un ReplicaSet ?**

Les Deployments ajoutent :
- Rolling updates (mises à jour progressives)
- Rollback (retour en arrière)
- Historique des versions
- Stratégies de déploiement configurables

**Exemple complet** :
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  labels:
    app: nginx
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Combien de pods en plus pendant la mise à jour
      maxUnavailable: 1  # Combien de pods peuvent être indisponibles
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
        ports:
        - containerPort: 80
```

**Rolling Update - Comment ça marche en détail ?**

Imaginons que vous ayez 3 répliques de nginx:1.20 et que vous voulez passer à nginx:1.21.

1. **État initial** :
   - ReplicaSet-v1 avec 3 pods nginx:1.20

2. **Lancement du rolling update** (kubectl apply ou kubectl set image) :
   - Kubernetes crée un nouveau ReplicaSet-v2 avec 0 répliques
   - Le Deployment controller commence l'orchestration

3. **Progression** (avec maxSurge=1, maxUnavailable=1) :
   
   Étape 1 :
   - ReplicaSet-v2 : scale à 1 pod (nouveau pod nginx:1.21 créé)
   - ReplicaSet-v1 : toujours 3 pods
   - Total : 4 pods (3 anciens + 1 nouveau) - respecte maxSurge=1
   
   Étape 2 (une fois que le nouveau pod est Ready) :
   - ReplicaSet-v1 : scale down à 2 pods (1 ancien pod supprimé)
   - ReplicaSet-v2 : toujours 1 pod
   - Total : 3 pods
   
   Étape 3 :
   - ReplicaSet-v2 : scale à 2 pods
   - ReplicaSet-v1 : toujours 2 pods
   - Total : 4 pods
   
   Étape 4 :
   - ReplicaSet-v1 : scale à 1 pod
   - ReplicaSet-v2 : toujours 2 pods
   - Total : 3 pods
   
   Étape 5 :
   - ReplicaSet-v2 : scale à 3 pods
   - ReplicaSet-v1 : toujours 1 pod
   - Total : 4 pods
   
   Étape finale :
   - ReplicaSet-v1 : scale à 0 pods (tous les anciens pods supprimés)
   - ReplicaSet-v2 : 3 pods (tous les nouveaux pods actifs)

4. **Fin** :
   - L'ancien ReplicaSet reste (avec 0 répliques) pour permettre le rollback
   - L'historique est conservé (par défaut les 10 dernières révisions)

**Readiness Probes et Rolling Updates**

Pour qu'un rolling update soit sûr, Kubernetes attend que chaque nouveau pod soit "Ready" :

```yaml
spec:
  containers:
  - name: nginx
    image: nginx:1.21
    readinessProbe:
      httpGet:
        path: /health
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 5
```

- Le pod n'est considéré Ready que si la readiness probe réussit
- Kubernetes n'arrête pas l'ancien pod tant que le nouveau n'est pas Ready
- Cela garantit qu'il y a toujours au moins X pods disponibles (où X = replicas - maxUnavailable)

**Rollback**

Si la mise à jour échoue :

```bash
# Voir l'historique
kubectl rollout history deployment/nginx-deployment

# Revenir à la version précédente
kubectl rollout undo deployment/nginx-deployment

# Revenir à une version spécifique
kubectl rollout undo deployment/nginx-deployment --to-revision=2
```

**Stratégies de Déploiement**

1. **RollingUpdate** (par défaut) :
   - Mise à jour progressive comme décrit ci-dessus
   - Pas d'interruption de service
   - Coexistence temporaire des anciennes et nouvelles versions

2. **Recreate** :
   - Tous les anciens pods sont supprimés
   - Puis tous les nouveaux pods sont créés
   - Interruption de service
   - Utile pour des applications qui ne peuvent pas avoir plusieurs versions simultanées

#### D. Service

**Définition** : Un Service est une abstraction qui définit un ensemble logique de Pods et une politique d'accès à ces Pods.

**Problème résolu** :
- Les Pods ont des IPs éphémères (changent quand pod redémarre)
- Comment faire communiquer des composants si les IPs changent ?
- Comment load-balancer entre plusieurs répliques d'un Pod ?

**Solution** : Le Service fournit une IP virtuelle stable et un DNS

**Types de Services** :

1. **ClusterIP** (défaut) :
   - Expose le service sur une IP interne au cluster
   - Accessible uniquement depuis l'intérieur du cluster
   - Use case : communication inter-services

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  type: ClusterIP
  selector:
    app: backend
  ports:
  - protocol: TCP
    port: 80        # Port du service
    targetPort: 8080 # Port du container
```

2. **NodePort** :
   - Expose le service sur un port de chaque nœud du cluster
   - Accessible depuis l'extérieur via <NodeIP>:<NodePort>
   - Port range : 30000-32767
   - Use case : tests, environnements de dev

```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
spec:
  type: NodePort
  selector:
    app: frontend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
    nodePort: 30080  # Optionnel, sinon auto-assigné
```

3. **LoadBalancer** :
   - Crée un load balancer externe (fourni par le cloud provider)
   - Distribue automatiquement le trafic vers les NodePorts
   - Use case : exposer une application en production sur le cloud
   - Coût : chaque LoadBalancer = un load balancer cloud (facturé)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: app-service
spec:
  type: LoadBalancer
  selector:
    app: myapp
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
```

4. **ExternalName** :
   - Mappe un service à un nom DNS externe
   - Ne fait pas de proxy, juste du DNS
   - Use case : accéder à une base de données externe

**Comment un Service fonctionne techniquement ?**

1. **Création** :
   - Vous créez un Service avec un selector
   - L'API server assigne une ClusterIP (virtuelle) au Service

2. **Endpoints** :
   - Le contrôleur d'endpoints surveille les Pods correspondant au selector
   - Il crée/maintient un objet Endpoints listant toutes les IPs des Pods
   - Cet objet est mis à jour en temps réel quand des Pods sont ajoutés/supprimés

3. **Routage** :
   - kube-proxy sur chaque nœud surveille les Services et Endpoints
   - Il configure iptables (ou IPVS) pour router le trafic
   - Quand un paquet arrive sur la ClusterIP, iptables le redirige vers un Pod

**Exemple concret** :

Service : ClusterIP = 10.100.200.50:80
Pods backend : 
- 10.244.1.5:8080
- 10.244.2.7:8080
- 10.244.3.9:8080

Règle iptables créée par kube-proxy :
```
Si destination = 10.100.200.50:80
Alors DNAT vers {10.244.1.5:8080, 10.244.2.7:8080, 10.244.3.9:8080} (load-balanced)
```

**Service Discovery** :

Kubernetes offre deux méthodes :

1. **DNS** (recommandé) :
   - Chaque Service obtient un nom DNS : `<service-name>.<namespace>.svc.cluster.local`
   - Exemple : `backend-service.default.svc.cluster.local`
   - CoreDNS (ou kube-dns) résout ce nom vers la ClusterIP
   - Les pods peuvent simplement appeler `http://backend-service/api`

2. **Variables d'environnement** :
   - Kubernetes injecte des variables pour chaque Service dans les Pods
   - Exemple : `BACKEND_SERVICE_SERVICE_HOST=10.100.200.50`
   - Limitation : le Service doit exister AVANT la création du Pod

#### E. Namespace

**Définition** : Un Namespace est un cluster virtuel à l'intérieur d'un cluster physique Kubernetes. C'est un mécanisme d'isolation.

**Namespaces par défaut** :
- `default` : namespace par défaut
- `kube-system` : objets créés par Kubernetes (DNS, dashboard, etc.)
- `kube-public` : lisible par tous, usage rare
- `kube-node-lease` : objets de heartbeat des nœuds

**Use cases** :
- Séparer les environnements (dev, staging, prod) dans un même cluster
- Isolation entre équipes/projets
- Quotas de ressources par namespace
- Politiques de sécurité (RBAC) par namespace

**Exemple** :
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: production  # Ce deployment sera dans le namespace "production"
spec:
  replicas: 5
  # ...
```

**Resource Quotas** :
```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: compute-quota
  namespace: development
spec:
  hard:
    requests.cpu: "10"      # Max 10 CPUs demandés
    requests.memory: 20Gi   # Max 20GB RAM demandée
    pods: "50"              # Max 50 pods
```

#### F. ConfigMap et Secret

**ConfigMap** : Stocke des données de configuration non-confidentielles sous forme clé-valeur.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  database_url: "postgres://db.example.com:5432"
  log_level: "info"
  config.json: |
    {
      "feature_flags": {
        "new_ui": true
      }
    }
```

Utilisation dans un Pod :
```yaml
spec:
  containers:
  - name: app
    image: myapp:1.0
    envFrom:
    - configMapRef:
        name: app-config  # Toutes les clés deviennent des variables d'environnement
    # OU
    env:
    - name: DATABASE_URL
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: database_url
    # OU monter comme volume
    volumeMounts:
    - name: config-volume
      mountPath: /etc/config
  volumes:
  - name: config-volume
    configMap:
      name: app-config
```

**Secret** : Comme ConfigMap mais pour des données sensibles (passwords, tokens, clés).

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
data:
  username: YWRtaW4=      # "admin" en base64
  password: cGFzc3dvcmQ=  # "password" en base64
```

**Différences importantes** :
- Les Secrets sont stockés en base64 (pas un chiffrement !)
- Dans etcd, les Secrets peuvent être chiffrés at-rest (option à activer)
- Les Secrets ne sont transmis qu'aux nœuds qui en ont besoin
- Les Secrets sont montés en tmpfs (RAM, jamais écrit sur disque du nœud)

#### G. Volume et PersistentVolume

**Problème** : Les conteneurs sont éphémères, leurs données sont perdues au redémarrage.

**Solution** : Les Volumes Kubernetes

**Types de volumes** :

1. **emptyDir** :
   - Créé quand le Pod est assigné à un nœud
   - Existe tant que le Pod existe
   - Partagé entre conteneurs du même Pod
   - Données perdues si Pod supprimé

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: cache
      mountPath: /cache
  volumes:
  - name: cache
    emptyDir: {}
```

2. **hostPath** :
   - Monte un fichier/dossier du nœud dans le Pod
   - Dangereux en prod (dépendance au nœud spécifique)

3. **PersistentVolume (PV)** et **PersistentVolumeClaim (PVC)** :

**Architecture en 3 couches** :

- **Storage Class** : Définit le "type" de stockage (AWS EBS, GCE Persistent Disk, NFS, etc.)
- **PersistentVolume (PV)** : Représentation d'un volume de stockage dans le cluster
- **PersistentVolumeClaim (PVC)** : Demande de stockage par un utilisateur

**Flux** :
1. Admin crée un PV (ou provision dynamique via StorageClass)
2. Utilisateur crée un PVC (demande : "je veux 10GB de stockage SSD")
3. Kubernetes "bind" le PVC à un PV compatible
4. Pod utilise le PVC

```yaml
# PersistentVolume
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-1
spec:
  capacity:
    storage: 10Gi
  accessModes:
  - ReadWriteOnce   # RWO = un seul nœud, RWX = plusieurs nœuds
  persistentVolumeReclaimPolicy: Retain  # Retain, Delete, Recycle
  storageClassName: fast
  awsElasticBlockStore:
    volumeID: vol-0a1b2c3d4e5f
    fsType: ext4

---
# PersistentVolumeClaim
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: fast

---
# Pod utilisant le PVC
spec:
  containers:
  - name: app
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: my-pvc
```

**Dynamic Provisioning** :

Au lieu de créer des PV manuellement, on peut laisser Kubernetes les créer automatiquement :

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs  # Pilote de stockage
parameters:
  type: gp3
  iops: "3000"
  encrypted: "true"
```

Quand un PVC est créé avec `storageClassName: fast-ssd`, Kubernetes :
1. Appelle le provisioner (AWS EBS dans ce cas)
2. Crée automatiquement un volume EBS
3. Crée automatiquement le PV correspondant
4. Bind le PVC au PV

### 1.4 Concepts Avancés de Kubernetes

#### A. DaemonSet

**Définition** : Assure qu'une copie d'un Pod tourne sur tous (ou certains) nœuds.

**Use cases** :
- Agents de monitoring (Prometheus Node Exporter, Datadog agent)
- Agents de logs (Fluentd, Filebeat)
- Pilotes de stockage (Ceph, GlusterFS)
- Networking (kube-proxy, Calico)

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: logging-agent
spec:
  selector:
    matchLabels:
      app: logging
  template:
    metadata:
      labels:
        app: logging
    spec:
      containers:
      - name: fluentd
        image: fluentd:latest
```

**Comportement** :
- Quand un nouveau nœud rejoint le cluster → un pod est automatiquement créé dessus
- Quand un nœud est retiré → le pod est supprimé
- Les DaemonSets ignorent les taints non-tolérés

#### B. StatefulSet

**Définition** : Gère des applications stateful (avec état).

**Différences avec Deployment** :
- Identité stable et prévisible des Pods (nom fixe)
- Ordre de création/suppression garanti
- Stockage stable (chaque Pod a son propre PVC)

**Use cases** : Bases de données, systèmes distribués (Kafka, Elasticsearch, Cassandra)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: "mysql"  # Headless service requis
  replicas: 3
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
  volumeClaimTemplates:  # Chaque pod aura son propre volume
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

**Comportement** :
- Pods nommés : mysql-0, mysql-1, mysql-2 (pas de hash aléatoire)
- Création séquentielle : mysql-0 doit être Running avant que mysql-1 soit créé
- Suppression inverse : mysql-2 supprimé avant mysql-1
- Chaque pod a son DNS stable : mysql-0.mysql.default.svc.cluster.local

#### C. Job et CronJob

**Job** : Exécute un Pod jusqu'à complétion réussie.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: batch-process
spec:
  completions: 5          # 5 pods doivent se terminer avec succès
  parallelism: 2          # 2 pods en parallèle max
  backoffLimit: 3         # 3 tentatives en cas d'échec
  template:
    spec:
      containers:
      - name: processor
        image: data-processor:1.0
        command: ["python", "process.py"]
      restartPolicy: OnFailure  # Important pour les Jobs
```

**CronJob** : Crée des Jobs selon un planning (comme cron Linux).

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup
spec:
  schedule: "0 2 * * *"   # Tous les jours à 2h du matin
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: backup-tool:1.0
          restartPolicy: OnFailure
```

#### D. Probes (Health Checks)

Kubernetes utilise 3 types de probes pour monitorer la santé des conteneurs :

1. **Liveness Probe** : Est-ce que le conteneur est vivant ?
   - Si échoue → Kubernetes redémarre le conteneur
   - Use case : détecter deadlocks, processus bloqués

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30  # Attendre 30s après démarrage
  periodSeconds: 10        # Vérifier toutes les 10s
  timeoutSeconds: 5        # Timeout après 5s
  failureThreshold: 3      # 3 échecs consécutifs = conteneur redémarré
```

2. **Readiness Probe** : Est-ce que le conteneur est prêt à recevoir du trafic ?
   - Si échoue → Pod retiré des endpoints du Service (pas de trafic)
   - Si réussit → Pod ajouté aux endpoints
   - Use case : attendre que l'app soit prête (cache chargé, connexions DB établies)

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

3. **Startup Probe** : Est-ce que le conteneur a démarré ?
   - Pour des applications avec démarrage lent
   - Liveness et Readiness sont désactivées jusqu'à ce que Startup réussisse

**Types de probes** :
- `httpGet` : Appel HTTP GET (succès = status 200-399)
- `tcpSocket` : Tentative de connexion TCP (succès = connexion établie)
- `exec` : Exécute une commande (succès = exit code 0)

```yaml
livenessProbe:
  exec:
    command:
    - cat
    - /tmp/healthy
  initialDelaySeconds: 5
  periodSeconds: 5
```

#### E. Resources (Requests et Limits)

Kubernetes permet de spécifier les ressources CPU et mémoire pour chaque conteneur.

```yaml
resources:
  requests:     # Minimum garanti
    memory: "64Mi"
    cpu: "250m"   # 250 millicores = 0.25 CPU
  limits:       # Maximum autorisé
    memory: "128Mi"
    cpu: "500m"
```

**Requests** :
- Utilisé par le scheduler pour placer les Pods
- Garanti : le nœud réservera ces ressources
- Si un nœud n'a pas assez de CPU/RAM disponible, le Pod ne sera pas schedulé dessus

**Limits** :
- Maximum que le conteneur peut utiliser
- **CPU** : Si dépassé → throttling (conteneur ralenti)
- **Mémoire** : Si dépassé → OOMKilled (conteneur tué)

**QoS Classes** (Quality of Service) :

Kubernetes classe les Pods en 3 catégories pour l'éviction :

1. **Guaranteed** : requests = limits pour tous les conteneurs
   - Derniers à être évincés
   - Les plus protégés

2. **Burstable** : Au moins un conteneur a des requests < limits
   - Évincés en second

3. **BestEffort** : Aucune request ni limit
   - Premiers évincés
   - Moins protégés

**Exemple d'éviction** :

Si un nœud manque de mémoire :
1. Kubernetes évince d'abord les pods BestEffort
2. Puis les pods Burstable qui dépassent leurs requests
3. En dernier recours, les pods Guaranteed

#### F. Labels, Selectors et Annotations

**Labels** : Paires clé-valeur attachées aux objets Kubernetes.

```yaml
metadata:
  labels:
    app: frontend
    tier: web
    environment: production
    version: v1.2.3
```

**Selectors** : Filtrent les objets basés sur les labels.

- **Equality-based** : `app=frontend`, `tier!=backend`
- **Set-based** : `environment in (production, staging)`, `tier notin (cache)`

```bash
# kubectl avec selectors
kubectl get pods -l app=frontend
kubectl get pods -l 'environment in (prod,staging)'
kubectl get pods -l app=frontend,tier=web  # AND
```

**Annotations** : Métadonnées NON identifiantes (pas utilisées pour sélectionner).

```yaml
metadata:
  annotations:
    description: "Frontend web application"
    contact: "team-frontend@example.com"
    buildNumber: "12345"
    prometheus.io/scrape: "true"
    prometheus.io/port: "9090"
```

**Différence** :
- Labels : pour organiser et sélectionner
- Annotations : pour stocker des métadonnées arbitraires

#### G. Taints et Tolerations

Mécanisme pour contrôler quels Pods peuvent être schedulés sur quels nœuds.

**Taint** : Propriété sur un nœud qui repousse les Pods.

```bash
# Appliquer un taint
kubectl taint nodes node1 key=value:NoSchedule

# Effets possibles :
# - NoSchedule : aucun nouveau pod ne sera schedulé (sauf tolérants)
# - PreferNoSchedule : essaie d'éviter mais pas garanti
# - NoExecute : même les pods existants sont évincés (sauf tolérants)
```

**Toleration** : Propriété sur un Pod qui tolère un taint.

```yaml
spec:
  tolerations:
  - key: "key"
    operator: "Equal"
    value: "value"
    effect: "NoSchedule"
```

**Use cases** :
- Nœuds dédiés (ex: GPU) : `kubectl taint nodes gpu-node1 hardware=gpu:NoSchedule`
- Maintenance : `kubectl taint nodes node1 maintenance=true:NoExecute`
- Nœuds avec spot instances (préemptibles)

#### H. Affinity et Anti-Affinity

Mécanisme pour *attirer* les Pods vers certains nœuds.

**Node Affinity** : Préférences pour placer un Pod sur certains nœuds.

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:  # Hard requirement
        nodeSelectorTerms:
        - matchExpressions:
          - key: disktype
            operator: In
            values:
            - ssd
      preferredDuringSchedulingIgnoredDuringExecution:  # Soft preference
      - weight: 1
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values:
            - us-west-1a
```

**Pod Affinity** : Placer des Pods ensemble.

```yaml
spec:
  affinity:
    podAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - cache
        topologyKey: kubernetes.io/hostname  # Même nœud
```

**Pod Anti-Affinity** : Séparer des Pods.

```yaml
spec:
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - frontend
        topologyKey: kubernetes.io/hostname
```

**Use case** : S'assurer que les répliques d'une application sont sur des nœuds différents (haute disponibilité).

---

## 2. INGRESS CONTROLLER - CŒUR DU STAGE

### 2.1 Qu'est-ce qu'un Ingress ?

**Problème** :
- Les Services de type LoadBalancer créent un load balancer cloud par service (coûteux)
- Pas de routage HTTP avancé (path-based, host-based)
- Pas de gestion TLS centralisée

**Solution** : Ingress

Un **Ingress** est un objet Kubernetes qui gère l'accès externe HTTP/HTTPS vers les Services.

**Ingress vs Service** :
- Service (LoadBalancer) : Layer 4 (TCP/UDP)
- Ingress : Layer 7 (HTTP/HTTPS)

### 2.2 Architecture Ingress

**Composants** :

1. **Ingress Resource** : La définition des règles de routage (objet K8s)
2. **Ingress Controller** : Le logiciel qui implémente ces règles (ex: Nginx, Traefik, HAProxy)

**Flux de trafic** :

```
Internet
   ↓
Load Balancer (ou NodePort)
   ↓
Ingress Controller (Pod Nginx, par exemple)
   ↓
Service (ClusterIP)
   ↓
Pods
```

### 2.3 Ingress Resource - Exemples

**Simple host-based routing** :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: simple-ingress
spec:
  rules:
  - host: www.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

**Path-based routing** :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-ingress
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /v1
        pathType: Prefix
        backend:
          service:
            name: api-v1-service
            port:
              number: 8080
      - path: /v2
        pathType: Prefix
        backend:
          service:
            name: api-v2-service
            port:
              number: 8080
```

**TLS/HTTPS** :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tls-ingress
spec:
  tls:
  - hosts:
    - www.example.com
    secretName: tls-secret  # Secret contenant cert et key
  rules:
  - host: www.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

Le Secret TLS :
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tls-secret
type: kubernetes.io/tls
data:
  tls.crt: 
  tls.key: 
```

### 2.4 Ingress Controllers Populaires

**1. Nginx Ingress Controller**

Le plus populaire. Deux versions :
- **kubernetes/ingress-nginx** : Officiel, communautaire
- **nginxinc/kubernetes-ingress** : Commercial (Nginx Inc.)

**Architecture** :
- Déployé comme Deployment ou DaemonSet
- Utilise Nginx comme reverse proxy
- Surveille les objets Ingress via l'API Kubernetes
- Génère dynamiquement la configuration Nginx
- Reload Nginx quand configuration change

**Fonctionnalités** :
- Load balancing
- TLS termination
- Rate limiting
- Authentication (Basic, OAuth)
- Réécritures d'URL
- Sticky sessions
- WebSocket support

**Annotations spécifiques** :

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: basic-auth
```

**2. Traefik**

Reverse proxy moderne, conçu pour les microservices.

**Avantages** :
- Configuration automatique (service discovery)
- Dashboard intégré
- Support Let's Encrypt automatique
- Middleware riche
- Support multi-provider (K8s, Docker, Consul...)

**3. HAProxy Ingress**

Basé sur HAProxy, performant pour le TCP load balancing.

**4. Istio Gateway**

Partie d'un service mesh, offre des fonctionnalités avancées (circuit breaker, retry, observabilité).

### 2.5 Fonctionnalités Avancées d'un Ingress

#### A. Load Balancing

**Algorithmes** :
- Round Robin (par défaut)
- Least Connections
- IP Hash (sticky sessions)

Configuration Nginx :
```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/load-balance: "least_conn"
    nginx.ingress.kubernetes.io/upstream-hash-by: "$request_uri"  # Sticky
```

#### B. Sécurité

**1. Rate Limiting (Anti-DoS)** :

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "10"      # 10 requêtes/sec par IP
    nginx.ingress.kubernetes.io/limit-connections: "5"  # 5 connexions max par IP
```

**2. IP Whitelisting / Blacklisting** :

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,192.168.0.0/16"
```

**3. WAF (Web Application Firewall)** :

Intégration avec ModSecurity :
```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/enable-modsecurity: "true"
    nginx.ingress.kubernetes.io/enable-owasp-core-rules: "true"
```

**4. CORS (Cross-Origin Resource Sharing)** :

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://frontend.example.com"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "Authorization, Content-Type"
```

#### C. Observabilité

**1. Métriques Prometheus** :

Nginx Ingress expose des métriques Prometheus par défaut :

```
# Métriques clés :
nginx_ingress_controller_requests_total        # Nombre total de requêtes
nginx_ingress_controller_request_duration_seconds  # Latence
nginx_ingress_controller_response_size_bytes    # Taille des réponses
nginx_ingress_controller_ssl_expire_time_seconds  # Expiration certificats
```

**2. Logs** :

Nginx Ingress log chaque requête :
```
192.168.1.100 - [user@example.com] [10/Oct/2023:13:55:36 +0000] 
"GET /api/users HTTP/1.1" 200 1234 "https://example.com" 
"Mozilla/5.0" 123 0.456 [default-backend-80] 10.244.1.5:8080 1234 0.456 200
```

**Champs importants** :
- IP client
- Timestamp
- Méthode HTTP, Path, Status code
- Latence upstream
- Backend utilisé

**3. Tracing** :

Intégration avec Jaeger/Zipkin pour le tracing distribué :
```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/enable-opentracing: "true"
    nginx.ingress.kubernetes.io/jaeger-collector-host: jaeger-collector.default.svc.cluster.local
```

#### D. TLS et Certificats

**Gestion manuelle** :

```bash
# Créer un Secret TLS
kubectl create secret tls my-tls-secret \
  --cert=path/to/cert.crt \
  --key=path/to/key.key
```

**Cert-Manager (automatique)** :

Cert-Manager automatise la gestion des certificats (Let's Encrypt, etc.) :

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: example-com-cert
spec:
  secretName: example-com-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - example.com
  - www.example.com
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - example.com
    secretName: example-com-tls
  rules:
  - host: example.com
    # ...
```

Cert-Manager :
1. Détecte le nouvel Ingress
2. Crée un Challenge ACME (HTTP-01 ou DNS-01)
3. Obtient le certificat de Let's Encrypt
4. Crée le Secret avec le certificat
5. Renouvelle automatiquement avant expiration

### 2.6 Le Contexte du Stage - Service Ingress Indépendant

**Problème actuel chez 3DS OUTSCALE** :

Aujourd'hui, l'Ingress Controller est **couplé** au service "Container Farm" :
- Déployé EN MÊME TEMPS que le cluster Kubernetes
- Même cycle de vie
- Mise à jour de l'Ingress = mise à jour de tout le service Container Farm

**Problème** :
- Ingress Controller nécessite des mises à jour **fréquentes** (nouveaux features, patches de sécurité)
- Container Farm a un cycle de release plus **lent** et espacé
- Impossible de mettre à jour l'Ingress sans toucher à toute l'infrastructure

**Solution proposée** : Service Ingress **indépendant**

Objectifs du stage :
1. **Découpler** l'Ingress du Container Farm
2. Créer un **service SD-HELM** pour l'Ingress
3. Permettre des **mises à jour indépendantes**
4. **Rolling upgrade** sans interruption
5. **Opérations à distance** (maintenance, debug)
6. **Supervision complète** (métriques, logs, alertes)

**SD-HELM** : Framework interne de 3DS pour créer des services Kubernetes packagés avec Helm et intégrés aux standards OUTSCALE.Platform.

**Livrables attendus** :
- Chart Helm pour l'Ingress Controller
- Rolling upgrade sans downtime
- Commandes de maintenance exposées
- Collecte métriques et logs
- Critères d'alerte
- Plan de migration du mode actuel vers le nouveau mode

---

## 3. HELM - PACKAGE MANAGER POUR KUBERNETES

### 3.1 Introduction à Helm

**Définition** : Helm est un package manager pour Kubernetes, comme apt pour Debian ou npm pour Node.js.

**Problème résolu** :

Sans Helm :
```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
# ... 50 fichiers YAML
```

Avec Helm :
```bash
helm install myapp ./myapp-chart
```

**Concepts clés** :

1. **Chart** : Package Helm (équivalent d'un .deb ou .rpm)
   - Collection de fichiers YAML templatés
   - Structure standardisée

2. **Release** : Instance d'un chart déployé
   - Vous pouvez installer le même chart plusieurs fois avec des noms différents

3. **Repository** : Serveur hébergeant des charts
   - Artifacthub.io : registry public
   - Possibilité d'avoir des repos privés

### 3.2 Structure d'un Chart Helm

```
mychart/
├── Chart.yaml           # Métadonnées du chart
├── values.yaml          # Valeurs par défaut
├── templates/           # Templates Kubernetes
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── _helpers.tpl     # Fonctions template réutilisables
│   └── NOTES.txt        # Instructions post-installation
├── charts/              # Dépendances (sous-charts)
└── .helmignore          # Fichiers à ignorer
```

### 3.3 Chart.yaml

```yaml
apiVersion: v2
name: ingress-controller
description: Ingress Controller for OUTSCALE Platform
version: 1.0.0        # Version du chart
appVersion: "2.4.0"   # Version de l'application (Nginx dans ce cas)
type: application     # ou 'library'
dependencies:
  - name: common
    version: 1.0.0
    repository: https://charts.example.com
maintainers:
  - name: Team Platform
    email: platform@3ds.com
keywords:
  - ingress
  - nginx
  - loadbalancer
```

### 3.4 values.yaml - Configuration

```yaml
# values.yaml
replicaCount: 3

image:
  repository: nginx-ingress
  tag: "2.4.0"
  pullPolicy: IfNotPresent

service:
  type: LoadBalancer
  port: 80
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80

metrics:
  enabled: true
  serviceMonitor:
    enabled: true

tolerations: []
affinity: {}
nodeSelector: {}
```

### 3.5 Templates - Templating avec Go

Helm utilise le moteur de template Go.

**Exemple : templates/deployment.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "mychart.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "mychart.selectorLabels" . | nindent 8 }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: 80
          protocol: TCP
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
```

**Syntaxe des templates** :

- `{{ .Values.xxx }}` : Accès aux valeurs de values.yaml
- `{{ .Chart.xxx }}` : Accès aux métadonnées du Chart
- `{{ .Release.xxx }}` : Informations sur la release (nom, namespace, etc.)
- `{{- ... }}` : Supprime les espaces avant
- `{{ ... -}}` : Supprime les espaces après
- `| nindent 4` : Indente de 4 espaces
- `| toYaml` : Convertit en YAML

**Fonctions utiles** :

- `{{ default "valeur-par-defaut" .Values.xxx }}`
- `{{ required "erreur si absent" .Values.xxx }}`
- `{{ quote .Values.xxx }}` : Ajoute des guillemets
- `{{ upper .Values.xxx }}` : Majuscules
- `{{ include "template-name" . }}` : Inclut un autre template

### 3.6 _helpers.tpl - Templates Réutilisables

```yaml
{{/*
Nom complet de l'application
*/}}
{{- define "mychart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Labels communs
*/}}
{{- define "mychart.labels" -}}
helm.sh/chart: {{ include "mychart.chart" . }}
{{ include "mychart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Labels de sélection
*/}}
{{- define "mychart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mychart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

### 3.7 Commandes Helm Essentielles

**Installation** :

```bash
# Installer un chart depuis un repo
helm install my-release stable/nginx-ingress

# Installer depuis un dossier local
helm install my-release ./mychart

# Avec valeurs personnalisées
helm install my-release ./mychart -f custom-values.yaml

# Ou avec --set
helm install my-release ./mychart \
  --set replicaCount=5 \
  --set image.tag=latest

# Dans un namespace spécifique
helm install my-release ./mychart -n production --create-namespace
```

**Upgrade** :

```bash
# Mettre à jour une release
helm upgrade my-release ./mychart

# Upgrade avec nouvelles valeurs
helm upgrade my-release ./mychart -f new-values.yaml

# Upgrade ou install si n'existe pas
helm upgrade --install my-release ./mychart
```

**Rollback** :

```bash
# Voir l'historique
helm history my-release

# Revenir à la version précédente
helm rollback my-release

# Revenir à une révision spécifique
helm rollback my-release 3
```

**Autres commandes** :

```bash
# Lister les releases
helm list
helm list -n production
helm list --all-namespaces

# Voir le statut
helm status my-release

# Désinstaller
helm uninstall my-release

# Voir les valeurs utilisées
helm get values my-release

# Voir tous les manifests générés
helm get manifest my-release

# Template (générer sans installer)
helm template my-release ./mychart
helm template my-release ./mychart -f values.yaml > output.yaml

# Valider un chart
helm lint ./mychart

# Packager un chart
helm package ./mychart
# Crée: mychart-1.0.0.tgz
```

### 3.8 Rolling Upgrade avec Helm

Helm intègre les rolling updates de Kubernetes :

```yaml
# Dans templates/deployment.yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # Zero downtime
```

Quand vous faites `helm upgrade` :
1. Helm génère les nouveaux manifests
2. Applique les changements via `kubectl apply`
3. Kubernetes effectue le rolling update (comme décrit section 1.3.C)
4. Helm attend que tous les pods soient Ready
5. Si échec : `helm rollback` restaure l'ancienne version

**Hooks Helm** pour contrôler le cycle de vie :

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "mychart.fullname" . }}-pre-upgrade
  annotations:
    "helm.sh/hook": pre-upgrade
    "helm.sh/hook-weight": "1"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  template:
    spec:
      containers:
      - name: pre-upgrade
        image: busybox
        command: ['sh', '-c', 'echo Pre-upgrade check']
      restartPolicy: Never
```

**Hooks disponibles** :
- `pre-install`, `post-install`
- `pre-upgrade`, `post-upgrade`
- `pre-rollback`, `post-rollback`
- `pre-delete`, `post-delete`
- `test` : pour les tests

### 3.9 Tests Helm

```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "mychart.fullname" . }}-test-connection"
  annotations:
    "helm.sh/hook": test
spec:
  containers:
  - name: wget
    image: busybox
    command: ['wget']
    args: ['{{ include "mychart.fullname" . }}:{{ .Values.service.port }}']
  restartPolicy: Never
```

Exécuter les tests :
```bash
helm test my-release
```

### 3.10 Best Practices Helm

1. **Valeurs par défaut fonctionnelles** : values.yaml doit permettre une installation sans config
2. **Documentation** : Commenter values.yaml
3. **Validation** : Utiliser `required` pour les valeurs obligatoires
4. **Idempotence** : `helm upgrade` doit pouvoir être appelé plusieurs fois sans problème
5. **Resources** : Toujours spécifier requests et limits
6. **Probes** : Inclure liveness et readiness probes
7. **Security** : Ne jamais hardcoder de secrets dans le chart
8. **NOTES.txt** : Fournir des instructions claires post-installation

```yaml
# templates/NOTES.txt
Thank you for installing {{ .Chart.Name }}.

Your release is named {{ .Release.Name }}.

To access your application:

{{- if .Values.ingress.enabled }}
  http{{ if .Values.ingress.tls }}s{{ end }}://{{ .Values.ingress.hostname }}/
{{- else }}
  export POD_NAME=$(kubectl get pods -n {{ .Release.Namespace }} -l "app.kubernetes.io/name={{ include "mychart.name" . }}" -o jsonpath="{.items[0].metadata.name}")
  kubectl port-forward $POD_NAME 8080:80
  echo "Visit http://127.0.0.1:8080"
{{- end }}
```

---

## 4. CONTENEURISATION AVEC DOCKER

### 4.1 Qu'est-ce que Docker ?

**Définition** : Docker est une plateforme de conteneurisation qui permet d'empaqueter une application avec toutes ses dépendances dans un conteneur standardisé.

**Conteneur vs Machine Virtuelle** :

**VM** :
```
Application
    ↓
OS Invité complet (Linux, Windows...)
    ↓
Hypervisor (VMware, VirtualBox)
    ↓
OS Hôte
    ↓
Hardware
```

**Conteneur** :
```
Application
    ↓
Librairies & dépendances
    ↓
Container Runtime (Docker)
    ↓
OS Hôte (partagé)
    ↓
Hardware
```

**Avantages des conteneurs** :
- Légers (Mo vs Go)
- Démarrage rapide (secondes vs minutes)
- Portabilité (même conteneur dev/prod)
- Densité (plus de conteneurs par machine)

### 4.2 Architecture Docker

**Composants** :

1. **Docker Client** : CLI (`docker` command)
2. **Docker Daemon** : Serveur qui gère les conteneurs
3. **Docker Registry** : Stocke les images (Docker Hub, Artifactory)
4. **Images** : Template read-only pour créer des conteneurs
5. **Conteneurs** : Instances en cours d'exécution d'images

### 4.3 Images Docker

**Qu'est-ce qu'une image ?**

Une image est composée de couches (layers) empilées :

```
Couche 4: COPY app.py /app     [Votre app]
Couche 3: RUN pip install flask [Dépendances]
Couche 2: RUN apt-get install python [Runtime]
Couche 1: FROM ubuntu:22.04    [OS de base]
```

Chaque couche est immuable et partagée entre images.

**Dockerfile** :

```dockerfile
# Image de base
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="dev@example.com"
LABEL version="1.0"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    APP_HOME=/app

# Créer un utilisateur non-root (sécurité)
RUN useradd -m -u 1000 appuser

# Répertoire de travail
WORKDIR $APP_HOME

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Changer le propriétaire
RUN chown -R appuser:appuser $APP_HOME

# Basculer vers l'utilisateur non-root
USER appuser

# Port exposé (documentation)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Commande par défaut
CMD ["python", "app.py"]
```

**Instructions Dockerfile** :

- `FROM` : Image de base
- `RUN` : Exécute une commande (crée une couche)
- `COPY` : Copie des fichiers depuis l'hôte
- `ADD` : Comme COPY mais peut télécharger URLs et extraire archives
- `WORKDIR` : Change le répertoire courant
- `ENV` : Définit des variables d'environnement
- `EXPOSE` : Documente les ports (pas d'effet réel)
- `USER` : Change l'utilisateur
- `CMD` : Commande par défaut (peut être overridden)
- `ENTRYPOINT` : Commande d'entrée (difficile à override)
- `VOLUME` : Définit un point de montage

**Best Practices** :

1. **Images minimales** : Utiliser des images de base slim/alpine
   ```dockerfile
   FROM python:3.11-alpine  # 50MB au lieu de 900MB
   ```

2. **Multi-stage builds** : Réduire la taille finale
   ```dockerfile
   # Stage 1: Build
   FROM golang:1.21 AS builder
   WORKDIR /app
   COPY . .
   RUN go build -o myapp
   
   # Stage 2: Runtime
   FROM alpine:3.18
   COPY --from=builder /app/myapp /usr/local/bin/
   CMD ["myapp"]
   ```

3. **Ordre des couches** : Mettre ce qui change rarement en premier
   ```dockerfile
   COPY requirements.txt .    # Change rarement
   RUN pip install -r requirements.txt
   COPY . .                   # Change souvent (code)
   ```

4. **Combiner les RUN** :
   ```dockerfile
   # Mauvais (3 couches)
   RUN apt-get update
   RUN apt-get install -y curl
   RUN apt-get clean
   
   # Bon (1 couche)
   RUN apt-get update && \
       apt-get install -y curl && \
       apt-get clean && \
       rm -rf /var/lib/apt/lists/*
   ```

5. **.dockerignore** : Exclure les fichiers inutiles
   ```
   .git
   .gitignore
   README.md
   .env
   *.pyc
   __pycache__
   node_modules
   ```

### 4.4 Commandes Docker

**Images** :

```bash
# Construire une image
docker build -t myapp:1.0 .
docker build -t myapp:1.0 -f Dockerfile.prod .

# Lister les images
docker images

# Supprimer une image
docker rmi myapp:1.0

# Inspecter une image
docker image inspect myapp:1.0

# Voir l'historique (couches)
docker history myapp:1.0

# Tag
docker tag myapp:1.0 registry.example.com/myapp:1.0

# Push vers un registry
docker push registry.example.com/myapp:1.0

# Pull depuis un registry
docker pull nginx:1.21
```

**Conteneurs** :

```bash
# Lancer un conteneur
docker run -d --name mycontainer -p 8080:80 nginx:1.21
# -d : détaché (background)
# --name : nom du conteneur
# -p : mapping de port (host:container)

# Avec variables d'env
docker run -e DATABASE_URL=postgres://... myapp:1.0

# Avec volumes
docker run -v /host/path:/container/path myapp:1.0

# Lister les conteneurs en cours
docker ps

# Lister tous les conteneurs (y compris arrêtés)
docker ps -a

# Logs d'un conteneur
docker logs mycontainer
docker logs -f mycontainer  # Follow (tail -f)
docker logs --tail 100 mycontainer

# Entrer dans un conteneur
docker exec -it mycontainer /bin/bash
docker exec mycontainer ls /app

# Arrêter un conteneur
docker stop mycontainer

# Démarrer un conteneur arrêté
docker start mycontainer

# Redémarrer
docker restart mycontainer

# Supprimer un conteneur
docker rm mycontainer
docker rm -f mycontainer  # Force (même si running)

# Voir les stats (CPU, RAM)
docker stats
docker stats mycontainer

# Inspecter
docker inspect mycontainer
```

**Volumes** :

```bash
# Créer un volume
docker volume create myvolume

# Lister les volumes
docker volume ls

# Utiliser un volume
docker run -v myvolume:/data myapp:1.0

# Inspecter un volume
docker volume inspect myvolume

# Supprimer un volume
docker volume rm myvolume

# Supprimer les volumes non utilisés
docker volume prune
```

**Réseau** :

```bash
# Créer un réseau
docker network create mynetwork

# Lister les réseaux
docker network ls

# Lancer des conteneurs sur le même réseau
docker run -d --name db --network mynetwork postgres:14
docker run -d --name app --network mynetwork myapp:1.0
# app peut appeler db via "http://db:5432"

# Inspecter un réseau
docker network inspect mynetwork
```

**Nettoyage** :

```bash
# Supprimer les conteneurs arrêtés
docker container prune

# Supprimer les images non utilisées
docker image prune

# Supprimer les volumes non utilisés
docker volume prune

# Nettoyage complet
docker system prune -a
```

### 4.5 Docker Compose

Pour gérer des applications multi-conteneurs.

**docker-compose.yml** :

```yaml
version: '3.8'

services:
  web:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - API_URL=http://api:8000
    depends_on:
      - api
    networks:
      - frontend

  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgres://db:5432/mydb
      - REDIS_URL=redis://cache:6379
    depends_on:
      - db
      - cache
    networks:
      - frontend
      - backend
    volumes:
      - ./backend:/app

  db:
    image: postgres:14
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - backend

  cache:
    image: redis:7-alpine
    networks:
      - backend

networks:
  frontend:
  backend:

volumes:
  db-data:
```

**Commandes Docker Compose** :

```bash
# Démarrer tous les services
docker-compose up
docker-compose up -d  # Détaché

# Voir les logs
docker-compose logs
docker-compose logs -f api  # Follow logs du service api

# Arrêter
docker-compose stop

# Arrêter et supprimer
docker-compose down
docker-compose down -v  # Aussi supprimer les volumes

# Rebuild les images
docker-compose build
docker-compose up --build

# Scaler un service
docker-compose up -d --scale api=3

# Exécuter une commande
docker-compose exec api python manage.py migrate
```

### 4.6 Container Runtime Interface (CRI)

Kubernetes ne parle pas directement à Docker. Il utilise une interface standardisée : CRI.

**Runtimes compatibles CRI** :
- **containerd** : Runtime par défaut de Kubernetes (léger, performant)
- **CRI-O** : Runtime optimisé pour Kubernetes
- **Docker** (via dockershim, deprecated depuis K8s 1.24)

**containerd** est aujourd'hui le standard :
```bash
# Avec containerd, on utilise crictl au lieu de docker
crictl ps
crictl images
crictl logs 
```

### 4.7 OCI (Open Container Initiative)

Standardisation des images et runtimes de conteneurs.

**OCI Image Spec** : Format d'image standardisé
- Toutes les images Docker sont OCI-compliant
- Buildah, Podman créent aussi des images OCI

**OCI Runtime Spec** : Comment exécuter un conteneur
- runc : runtime de référence (utilisé par Docker, containerd)

---

## 5. CLOUD COMPUTING ET AWS

### 5.1 Introduction au Cloud Computing

**Modèles de service** :

1. **IaaS** (Infrastructure as a Service) :
   - Machines virtuelles, stockage, réseau
   - Exemples : AWS EC2, Google Compute Engine
   - Vous gérez : OS, middleware, applications

2. **PaaS** (Platform as a Service) :
   - Plateforme pour déployer des applications
   - Exemples : AWS Elastic Beanstalk, Google App Engine
   - Vous gérez : applications, données

3. **SaaS** (Software as a Service) :
   - Applications prêtes à l'emploi
   - Exemples : Gmail, Salesforce, Office 365
   - Vous gérez : rien, juste l'utilisation

4. **CaaS** (Container as a Service) :
   - Orchestration de conteneurs managée
   - Exemples : AWS ECS, Google GKE, Azure AKS

### 5.2 AWS - Services Pertinents pour Kubernetes

#### A. EC2 (Elastic Compute Cloud)

**Définition** : Machines virtuelles dans le cloud.

**Types d'instances** :
- **General Purpose** (t3, m5) : Équilibre CPU/RAM
- **Compute Optimized** (c5) : CPU intensif
- **Memory Optimized** (r5) : RAM intensive
- **Storage Optimized** (i3) : I/O intensif

**Utilisation avec Kubernetes** :
- Les Worker Nodes sont des instances EC2
- Les nœuds du Control Plane aussi (sauf EKS managé)

#### B. EKS (Elastic Kubernetes Service)

**Définition** : Kubernetes managé par AWS.

**Architecture** :
- AWS gère le Control Plane (API server, etcd, etc.)
- Vous gérez les Worker Nodes (EC2 ou Fargate)

**Avantages** :
- Haute disponibilité du Control Plane (multi-AZ)
- Intégration avec IAM, VPC, Load Balancers
- Mise à jour automatique du Control Plane

**Concepts EKS** :

1. **Node Groups** :
   - Groupes d'instances EC2 managés
   - Auto-scaling
   - Plusieurs node groups possibles (différents types d'instances)

2. **Fargate** :
   - Exécution de pods sans gérer de nœuds
   - Serverless pour Kubernetes
   - Facturation par pod

#### C. ELB (Elastic Load Balancer)

**Types** :

1. **CLB** (Classic Load Balancer) :
   - Ancien, Layer 4 et 7
   - Moins de fonctionnalités

2. **ALB** (Application Load Balancer) :
   - Layer 7 (HTTP/HTTPS)
   - Routage basé sur le path, host, headers
   - WebSocket support
   - Intégration avec WAF

3. **NLB** (Network Load Balancer) :
   - Layer 4 (TCP/UDP)
   - Très haute performance
   - IP fixe
   - Préserve l'IP source du client

**Avec Kubernetes** :
- Service de type LoadBalancer → crée automatiquement un NLB ou CLB
- Ingress avec AWS Load Balancer Controller → crée un ALB

#### D. EBS (Elastic Block Store)

**Définition** : Volumes de stockage bloc pour EC2.

**Types** :
- **gp3/gp2** : SSD général
- **io2/io1** : SSD haute performance (IOPS provisionnés)
- **st1** : HDD optimisé débit
- **sc1** : HDD cold storage

**Avec Kubernetes** :
- PersistentVolume backend
- StorageClass avec provisioner EBS

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3-storage
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
```

#### E. Route53

**Définition** : Service DNS managé.

**Avec Kubernetes** :
- External-DNS : synchronise automatiquement les Ingress/Services avec Route53
- Crée/met à jour les enregistrements DNS quand vous créez des Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  annotations:
    external-dns.alpha.kubernetes.io/hostname: myapp.example.com
spec:
  rules:
  - host: myapp.example.com
    # ...
```

#### F. IAM (Identity and Access Management)

**Avec Kubernetes** :
- **IRSA** (IAM Roles for Service Accounts) :
  - Permet aux Pods d'assumer des rôles IAM
  - Accès sécurisé aux ressources AWS (S3, RDS, etc.)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/my-app-role
---
spec:
  serviceAccountName: my-app
  containers:
  - name: app
    # Ce pod peut maintenant accéder aux ressources autorisées par le rôle IAM
```

#### G. CloudWatch

**Définition** : Service de monitoring et logs.

**Avec Kubernetes** :
- CloudWatch Container Insights : métriques de cluster, nœuds, pods
- Log collection via Fluent Bit ou Fluentd

### 5.3 CDN (Content Delivery Network)

**Définition** : Réseau de serveurs distribués qui délivrent du contenu au plus près des utilisateurs.

**AWS CloudFront** :
- CDN d'AWS
- Cache le contenu statique (images, CSS, JS)
- Améliore la latence
- Protection DDoS

**Avec Kubernetes** :
- CloudFront en front d'un Ingress
- Origin : Load Balancer du cluster

```
User → CloudFront (edge locations) → ALB/NLB → Ingress → Service → Pods
```

---

## 6. DEVOPS ET OBSERVABILITÉ

### 6.1 Principes DevOps

**DevOps** = Culture + Pratiques + Outils pour raccourcir le cycle de développement.

**Principes** :
1. **Automatisation** : CI/CD, IaC
2. **Mesure** : Métriques, monitoring
3. **Partage** : Collaboration Dev/Ops
4. **Amélioration continue** : Feedback loops

### 6.2 CI/CD (Continuous Integration / Continuous Delivery)

**CI (Continuous Integration)** :
- Intégration fréquente du code
- Tests automatiques à chaque commit
- Build automatique

**CD (Continuous Delivery/Deployment)** :
- Delivery : Toujours prêt à déployer
- Deployment : Déploiement automatique en production

**Pipeline typique** :

```
Code Commit
   ↓
CI : Build & Test
   ↓
Build Docker Image
   ↓
Push to Registry
   ↓
Deploy to Kubernetes (Helm)
   ↓
Smoke Tests
   ↓
Production
```

**Outils** :
- **GitLab CI/CD, GitHub Actions, Jenkins, CircleCI**

**Exemple GitLab CI** :

```yaml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

test:
  stage: test
  script:
    - pytest tests/

deploy-staging:
  stage: deploy
  script:
    - helm upgrade --install myapp ./chart \
        --set image.tag=$CI_COMMIT_SHA \
        -n staging
  environment:
    name: staging

deploy-production:
  stage: deploy
  script:
    - helm upgrade --install myapp ./chart \
        --set image.tag=$CI_COMMIT_SHA \
        -n production
  environment:
    name: production
  when: manual  # Déploiement manuel en prod
```

### 6.3 Observabilité - Les 3 Piliers

#### A. Métriques

**Définition** : Valeurs numériques collectées au fil du temps.

**Types de métriques** :
- **Métriques d'infrastructure** : CPU, RAM, Disk, Network
- **Métriques d'application** : Requêtes/sec, latence, erreurs
- **Métriques métier** : Nombre d'utilisateurs, transactions, revenue

**Golden Signals** (Google SRE) :
1. **Latency** : Temps de réponse
2. **Traffic** : Volume de requêtes
3. **Errors** : Taux d'erreur
4. **Saturation** : Utilisation des ressources

**USE Method** (pour infrastructure) :
- **Utilization** : % d'utilisation d'une ressource
- **Saturation** : Travail en attente
- **Errors** : Nombre d'erreurs

**RED Method** (pour services) :
- **Rate** : Requêtes par seconde
- **Errors** : Nombre d'erreurs
- **Duration** : Temps de réponse

**Prometheus** : Système de monitoring de référence pour Kubernetes.

**Architecture Prometheus** :
```
Prometheus Server
   ↓ (scrape)
Targets (pods, services)
   ↓ (expose metrics)
/metrics endpoint
```

**Exposition de métriques** :

Application Python avec Prometheus client :
```python
from prometheus_client import Counter, Histogram, generate_latest

request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])

@app.route('/metrics')
def metrics():
    return generate_latest()

@app.route('/api/users')
def get_users():
    with request_duration.labels('GET', '/api/users').time():
        # ... logique métier ...
        request_count.labels('GET', '/api/users', '200').inc()
        return jsonify(users)
```

**ServiceMonitor** (Prometheus Operator) :

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp
spec:
  selector:
    matchLabels:
      app: myapp
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

**PromQL** : Langage de requête de Prometheus

```promql
# Taux de requêtes par seconde
rate(http_requests_total[5m])

# Latence p95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Taux d'erreur
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# CPU usage par pod
container_cpu_usage_seconds_total{pod="myapp-xyz"}
```

**Grafana** : Visualisation de métriques

- Dashboards
- Alerting
- Data sources (Prometheus, CloudWatch, etc.)

#### B. Logs

**Définition** : Enregistrements d'événements horodatés.

**Niveaux de logs** :
- DEBUG : Informations détaillées
- INFO : Informations générales
- WARNING : Avertissements
- ERROR : Erreurs
- CRITICAL : Erreurs fatales

**Structured Logging** (JSON) :

```json
{
  "timestamp": "2024-02-11T10:30:00Z",
  "level": "ERROR",
  "service": "api",
  "pod": "api-abc123",
  "trace_id": "xyz789",
  "message": "Database connection failed",
  "error": "connection timeout",
  "database": "postgres-primary"
}
```

**Avantages** :
- Facilement parsable
- Recherchable
- Corrélable avec métriques et traces

**Logging Stack (ELK/EFK)** :

1. **ELK** : Elasticsearch, Logstash, Kibana
2. **EFK** : Elasticsearch, Fluentd, Kibana

**Architecture** :
```
Pods (stdout/stderr)
   ↓
Fluentd (DaemonSet sur chaque nœud)
   ↓ (parse, filter, enrich)
Elasticsearch
   ↓ (visualize)
Kibana
```

**Fluentd Configuration** :

```xml

  @type tail
  path /var/log/containers/*.log
  pos_file /var/log/fluentd-containers.log.pos
  tag kubernetes.*
  
    @type json
    time_key timestamp
    time_format %Y-%m-%dT%H:%M:%S.%NZ
  



  @type kubernetes_metadata
  # Enrichit avec métadonnées K8s (namespace, pod name, labels...)



  @type elasticsearch
  host elasticsearch.logging.svc.cluster.local
  port 9200
  index_name kubernetes

```

#### C. Tracing

**Définition** : Suit une requête à travers plusieurs services (microservices).

**Distributed Tracing** :

Requête : User → API Gateway → Service A → Service B → Database

Trace = ensemble de spans :
- Span 1 : API Gateway (100ms)
  - Span 2 : Service A (70ms)
    - Span 3 : Service B (50ms)
      - Span 4 : Database query (30ms)

**OpenTelemetry** : Standard pour l'instrumentation.

**Jaeger** : Plateforme de tracing distribuée.

**Instrumentation** :

```python
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.exporter.jaeger import JaegerExporter

tracer = trace.get_tracer(__name__)

@app.route('/api/users/')
def get_user(user_id):
    with tracer.start_as_current_span("get_user"):
        with tracer.start_as_current_span("db_query"):
            user = db.query(User).filter_by(id=user_id).first()
        with tracer.start_as_current_span("format_response"):
            response = format_user(user)
        return jsonify(response)
```

**Trace Context Propagation** :

Les headers HTTP transportent le contexte de trace :
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

Chaque service propage ce contexte, permettant de reconstruire la trace complète.

### 6.4 Alerting

**Prometheus Alerts** :

```yaml
groups:
- name: example
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate on {{ $labels.service }}"
      description: "Error rate is {{ $value }} (threshold: 0.05)"

  - alert: PodCrashLooping
    expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Pod {{ $labels.pod }} is crash looping"

  - alert: HighMemoryUsage
    expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Container {{ $labels.container }} high memory usage"
```

**Alertmanager** : Gère les alertes (grouping, routing, silencing).

```yaml
route:
  receiver: 'team-frontend'
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  routes:
  - match:
      service: api
    receiver: 'team-backend'
  - match:
      severity: critical
    receiver: 'pagerduty'

receivers:
- name: 'team-frontend'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/XXX'
    channel: '#frontend-alerts'

- name: 'pagerduty'
  pagerduty_configs:
  - service_key: 'XXX'
```

---

## 7. SÉCURITÉ ET RÉSEAUX

### 7.1 TLS/HTTPS

**TLS** (Transport Layer Security) : Protocole de chiffrement pour les communications réseau.

**Composants** :
1. **Certificat** : Contient la clé publique + identité (domaine)
2. **Clé privée** : Utilisée pour déchiffrer
3. **CA** (Certificate Authority) : Signe les certificats (Let's Encrypt, DigiCert)

**Handshake TLS** :

```
Client → Server : Client Hello
Server → Client : Server Hello + Certificate
Client : Vérifie le certificat
Client → Server : Key Exchange (chiffré avec clé publique du serveur)
Les deux : Dérivent une clé symétrique
Communication chiffrée avec cette clé symétrique
```

**Chaîne de certificats** :

```
Root CA (trusted)
   ↓ (signs)
Intermediate CA
   ↓ (signs)
Site Certificate (www.example.com)
```

Le navigateur valide :
1. Le certificat est signé par une CA de confiance
2. Le domaine correspond (SAN - Subject Alternative Name)
3. Le certificat n'est pas expiré
4. Le certificat n'est pas révoqué (CRL/OCSP)

### 7.2 Reverse Proxy

**Définition** : Serveur qui fait l'interface entre les clients et les serveurs backend.

```
Clients
   ↓
Reverse Proxy (Nginx, HAProxy)
   ↓
Backend Servers
```

**Rôles** :
- Load balancing
- TLS termination
- Caching
- Compression
- Rate limiting
- WAF

**Nginx comme Reverse Proxy** :

```nginx
upstream backend {
    least_conn;  # Algorithme de load balancing
    server 10.0.1.5:8080 weight=3;
    server 10.0.1.6:8080 weight=2;
    server 10.0.1.7:8080 backup;  # Utilisé si les autres tombent
}

server {
    listen 443 ssl http2;
    server_name www.example.com;

    # TLS
    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Caching
    location ~* \.(jpg|jpeg|png|gif|css|js)$ {
        proxy_pass http://backend;
        proxy_cache my_cache;
        proxy_cache_valid 200 1h;
        add_header X-Cache-Status $upstream_cache_status;
    }
}
```

### 7.3 Networking dans Kubernetes

**Modèle réseau Kubernetes** :

Règles :
1. Tous les Pods peuvent communiquer avec tous les autres Pods sans NAT
2. Tous les Nodes peuvent communiquer avec tous les Pods sans NAT
3. L'IP qu'un Pod voit de lui-même est la même que les autres voient
