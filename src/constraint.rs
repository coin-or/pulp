//! Constraint handle (constraint stored in a ModelCore). Only created by Model.
//! Model is always present; no optional fallbacks.

use pyo3::prelude::*;
use std::cell::RefCell;
use std::rc::Weak;

use crate::format;
use crate::types::{upgrade_model, ConstrId, ModelCore, Sense};
use crate::variable::Variable;

/// Handle to a constraint stored inside a `ModelCore`. Only created by the model.
#[pyclass(unsendable)]
#[derive(Clone)]
pub struct Constraint {
    pub id: ConstrId,
    pub model: Weak<RefCell<ModelCore>>,
}

#[pymethods]
impl Constraint {
    fn id(&self) -> ConstrId {
        self.id
    }

    #[getter]
    fn name(&self) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints
            .get(self.id)
            .map(|c| c.name.clone())
            .unwrap_or_default()
    }

    fn set_name(&self, name: String) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.name = name;
        }
    }

    #[getter]
    fn pi(&self) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].pi
    }

    fn set_pi(&self, v: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.pi = Some(v);
        }
    }

    #[getter]
    fn slack(&self) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].slack
    }

    fn set_slack(&self, v: f64) {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let mut core = core_rc.borrow_mut();
        if let Some(c) = core.constraints.get_mut(self.id) {
            c.slack = Some(v);
        }
    }

    #[getter]
    fn sense(&self) -> Sense {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].sense
    }

    #[getter]
    fn rhs(&self) -> f64 {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        core.constraints[self.id].rhs
    }

    fn items(&self) -> Vec<(Variable, f64)> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let c = &core.constraints[self.id];
        c.coeffs
            .iter()
            .map(|(&var_id, &coeff)| {
                (
                    Variable {
                        id: var_id,
                        model: self.model.clone(),
                    },
                    coeff,
                )
            })
            .collect()
    }

    // ── Value / validation methods ──

    fn value(&self) -> Option<f64> {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let cd = &core.constraints[self.id];
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        let mut total = constant;
        for (&var_id, &coeff) in &cd.coeffs {
            let val = core.vars.get(var_id)?.value?;
            total += val * coeff;
        }
        Some(total)
    }

    fn value_or_default(&self) -> f64 {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let cd = &core.constraints[self.id];
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        let mut total = constant;
        for (&var_id, &coeff) in &cd.coeffs {
            if let Some(vd) = core.vars.get(var_id) {
                let v = vd.value.unwrap_or_else(|| format::default_value(vd.lb, vd.ub));
                total += v * coeff;
            }
        }
        total
    }

    #[pyo3(signature = (eps=0.0))]
    fn valid(&self, eps: f64) -> bool {
        let val = match self.value() {
            Some(v) => v,
            None => return false,
        };
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let cd = &core.constraints[self.id];
        match cd.sense {
            Sense::Equal => val.abs() <= eps,
            Sense::LessEqual => val * (-1.0) >= -eps,
            Sense::GreaterEqual => val >= -eps,
        }
    }

    // ── Formatting methods (delegate to format.rs) ──

    fn as_cplex_lp_constraint(&self, name: &str) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        let rhs = if cd.rhs == 0.0 { 0.0 } else { cd.rhs };
        format::cplex_lp_constraint(&sorted, cd.sense, rhs, name, cd.coeffs.is_empty())
    }

    #[pyo3(signature = (name, include_constant=true))]
    fn as_cplex_lp_affine_expression(&self, name: &str, include_constant: bool) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        format::cplex_lp_affine_expression(&sorted, constant, name, include_constant)
    }

    fn str_repr(&self) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        format::str_constraint(&sorted, cd.sense, -cd.rhs)
    }

    fn repr_str(&self) -> String {
        let core_rc = upgrade_model(&self.model).expect("model always present");
        let core = core_rc.borrow();
        let cd = &core.constraints[self.id];
        let sorted = format::sorted_pairs_from_coeffs(&cd.coeffs, &core);
        let constant = if cd.rhs == 0.0 { 0.0 } else { -cd.rhs };
        format::repr_expr(&sorted, constant, Some(cd.sense))
    }
}
