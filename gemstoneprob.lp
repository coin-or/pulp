\* The_Gemstone_Tool_Problem *\
Maximize
Total_cost: 25 production_0_pliers + 40 production_0_wrenches
 + 25 production_1_pliers + 40 production_1_wrenches + 25 production_2_pliers
 + 22.5 production_2_wrenches + 25 production_3_pliers
 + 22.5 production_3_wrenches - 58 steelpurchase
Subject To
Steel_capacity0: production_0_pliers + 1.5 production_0_wrenches
 - steelpurchase <= 0
Steel_capacity1: production_1_pliers + 1.5 production_1_wrenches
 - steelpurchase <= 0
Steel_capacity2: production_2_pliers + 1.5 production_2_wrenches
 - steelpurchase <= 0
Steel_capacity3: production_3_pliers + 1.5 production_3_wrenches
 - steelpurchase <= 0
assembly_capacity0: 0.5 production_0_pliers + 0.3 production_0_wrenches <= 8
assembly_capacity1: 0.5 production_1_pliers + 0.3 production_1_wrenches <= 10
assembly_capacity2: 0.5 production_2_pliers + 0.3 production_2_wrenches <= 8
assembly_capacity3: 0.5 production_3_pliers + 0.3 production_3_wrenches <= 10
capacity_pliers0: production_0_pliers <= 16
capacity_pliers1: production_1_pliers <= 16
capacity_pliers2: production_2_pliers <= 16
capacity_pliers3: production_3_pliers <= 16
capacity_wrenches0: production_0_wrenches <= 15
capacity_wrenches1: production_1_wrenches <= 15
capacity_wrenches2: production_2_wrenches <= 15
capacity_wrenches3: production_3_wrenches <= 15
molding_capacity0: production_0_pliers + production_0_wrenches <= 21
molding_capacity1: production_1_pliers + production_1_wrenches <= 21
molding_capacity2: production_2_pliers + production_2_wrenches <= 21
molding_capacity3: production_3_pliers + production_3_wrenches <= 21
End
